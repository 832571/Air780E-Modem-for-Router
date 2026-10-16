import json, smtplib, tempfile, unittest
from pathlib import Path
from unittest.mock import Mock, patch
import email_forward as mail
import sms_store
from signal_level import bars
class SignalTests(unittest.TestCase):
    def test_boundaries(self):
        for value,expected in [(-44,5),(-85,5),(-86,4),(-95,4),(-96,3),(-105,3),(-106,2),(-115,2),(-116,1),(-140,1)]:
            self.assertEqual(bars(value),expected)
    def test_unknown_not_full_bars(self):
        for value in (None,True,0,255,-141,'-90',float('nan')):
            self.assertIsNone(bars(value))
class MailTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(); self.store=Path(self.directory.name)
        self.config={'enabled':True,'host':'smtp.example.com','port':465,'tls':'SSL','username':'sender@example.com','sender':'sender@example.com','recipients':['one@example.com','two@example.com','three@example.com']}
    def tearDown(self): self.directory.cleanup()
    def incoming(self,ident):
        sms_store.save(self.store,dict(event='sms_received',sms_id=ident,number='10010',message='示例短信',received='now'))
    def test_validation(self):
        with self.assertRaises(ValueError): mail.validate(self.config|{'recipients':['a@example.com']*4+['b@example.com','c@example.com','d@example.com']})
        with self.assertRaises(ValueError): mail.validate(self.config|{'tls':'NONE'})
        with self.assertRaises(ValueError): mail.validate(self.config|{'sender':'bad\r\nBcc: x@example.com'})
        self.assertEqual(len(mail.validate(self.config)['recipients']),3)
    def test_config_never_keeps_password(self):
        mail.save(self.store,self.config|{'password':'private-test-placeholder'})
        content=(self.store/'email.json').read_text()
        self.assertNotIn('password',content);self.assertNotIn('private-test-placeholder',content)
        self.assertEqual((self.store/'email.json').stat().st_mode&0o777,0o600)
    def test_old_sms_not_forwarded_and_new_fans_out_once(self):
        self.incoming('old');mail.save(self.store,self.config);self.incoming('new')
        client=Mock();client.send_message.return_value={}
        with patch.object(mail,'session',return_value=client):
            mail.forward(self.store,'mock');mail.forward(self.store,'mock')
        self.assertEqual(client.send_message.call_count,3)
        self.assertEqual({r['sms_id'] for r in mail.history(self.store)},{'new'})
        self.assertTrue(all(r['state']=='sent' for r in mail.history(self.store)))
    def test_uncertain_not_automatically_resent(self):
        mail.save(self.store,self.config|{'recipients':['one@example.com']});self.incoming('new')
        client=Mock();client.send_message.side_effect=TimeoutError()
        with patch.object(mail,'session',return_value=client):
            mail.forward(self.store,'mock');mail.forward(self.store,'mock')
        self.assertEqual(client.send_message.call_count,1)
        self.assertEqual(mail.history(self.store)[0]['state'],'unknown')
    def test_connect_failure_does_not_mark_sent(self):
        mail.save(self.store,self.config);self.incoming('new')
        with patch.object(mail,'session',side_effect=ConnectionError()):
            with self.assertRaises(RuntimeError): mail.forward(self.store,'mock')
        self.assertEqual(mail.history(self.store),[])
    def test_auth_failure_blocks_repeated_login_until_saved(self):
        mail.save(self.store,self.config);self.incoming('new')
        with patch.object(mail,'session',side_effect=smtplib.SMTPAuthenticationError(535,b'bad')) as session:
            with self.assertRaises(RuntimeError): mail.forward(self.store,'mock')
            self.assertIn('暂停',mail.forward(self.store,'mock'))
            self.assertEqual(session.call_count,1)
        mail.save(self.store,self.config)
        self.assertFalse((self.store/'mail_retry.json').exists())
    def test_deleted_sms_not_forwarded(self):
        mail.save(self.store,self.config);self.incoming('new');sms_store.archive(self.store,['new'])
        with patch.object(mail,'session') as session: mail.forward(self.store,'mock');session.assert_not_called()
    def test_connection_test_sends_no_mail(self):
        mail.save(self.store,self.config);client=Mock()
        with patch.object(mail,'session',return_value=client):mail.test_connection(self.store,'mock')
        client.send_message.assert_not_called()
    def test_starttls_precedes_authentication(self):
        client=Mock()
        with patch.object(mail,'tls_context',return_value='verified-context'),patch.object(mail.smtplib,'SMTP',return_value=client):
            mail.session(self.config|{'tls':'STARTTLS'},'mock')
        self.assertEqual([c[0] for c in client.method_calls],['ehlo','starttls','ehlo','login'])

    def test_submission_timestamp_saved_before_smtp_and_survives_refresh(self):
        mail.save(self.store,self.config|{'recipients':['one@example.com']});self.incoming('new')
        client=Mock()
        def sending(*args,**kwargs):
            record=mail.history(self.store)[0]
            self.assertEqual(record['state'],'sending')
            self.assertEqual(record['submitted_at'],1792080000.0)
            return {}
        client.send_message.side_effect=sending
        with patch.object(mail,'session',return_value=client),patch.object(mail.time,'time',return_value=1792080000.0):
            mail.forward(self.store,'mock')
        self.assertEqual(mail.history(self.store)[0]['submitted_at'],1792080000.0)
        self.assertEqual(mail.history(self.store)[0]['state'],'sent')
        with patch.object(mail,'session') as session:
            mail.forward(self.store,'mock');session.assert_not_called()
        self.assertEqual(mail.history(self.store)[0]['submitted_at'],1792080000.0)

    def test_legacy_history_migration_preserves_unknown_time(self):
        with sms_store.connect(self.store) as db:
            db.execute('CREATE TABLE mail_delivery (sms_id TEXT, recipient TEXT, state TEXT, detail TEXT, PRIMARY KEY(sms_id,recipient))')
            db.execute("INSERT INTO mail_delivery VALUES ('old','one@example.com','sent','accepted')")
        for _ in range(2):
            record=mail.history(self.store)[0]
            self.assertEqual(record['sms_id'],'old')
            self.assertEqual(record['state'],'sent')
            self.assertIsNone(record['submitted_at'])
        mail.save(self.store,self.config|{'recipients':['one@example.com']});self.incoming('new')
        client=Mock();client.send_message.return_value={}
        with patch.object(mail,'session',return_value=client):mail.forward(self.store,'mock')
        self.assertIsInstance(mail.history(self.store)[0]['submitted_at'],float)

    def test_unknown_send_retains_attempt_time(self):
        mail.save(self.store,self.config|{'recipients':['one@example.com']});self.incoming('new')
        client=Mock();client.send_message.side_effect=TimeoutError()
        with patch.object(mail,'session',return_value=client),patch.object(mail.time,'time',return_value=1792080001.0):
            mail.forward(self.store,'mock')
        record=mail.history(self.store)[0]
        self.assertEqual(record['submitted_at'],1792080001.0)
        self.assertEqual(record['state'],'unknown')
