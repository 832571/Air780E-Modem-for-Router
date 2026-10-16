import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import sms_store
class TrashTests(unittest.TestCase):
    def test_clears_all_not_only_visible_500_and_preserves_other_lists(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Path(directory)
            with sms_store.connect(store) as db:
                db.executemany('INSERT INTO inbox (id,number,message,received,deleted) VALUES (?,?,?,?,?)',[(str(i),'10010','example','now',1) for i in range(510)])
                db.execute("INSERT INTO inbox (id,number,message,received,deleted) VALUES ('keep','10010','keep','now',0)")
            sms_store.sending(store,'sent','10010','keep sent')
            self.assertEqual(sms_store.clear_trash(store),510)
            self.assertEqual(sms_store.rows(store,'trash'),[])
            self.assertEqual(len(sms_store.rows(store)),1)
            self.assertEqual(len(sms_store.rows(store,'sent')),1)
            self.assertEqual(sms_store.clear_trash(store),0)
    def test_device_replay_cannot_resurrect_purged_sms(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Path(directory); frame=dict(event='sms_received',sms_id='id',number='10010',message='private mock body',received='now')
            sms_store.save(store,frame);sms_store.archive(store,['id']);sms_store.clear_trash(store)
            sms_store.save(store,frame);sms_store.archive(store,['id'],restore=True)
            self.assertEqual(sms_store.rows(store),[])
            with sms_store.connect(store) as db:
                self.assertEqual(db.execute('SELECT * FROM purged_sms').fetchone()['id'],'id')
                self.assertEqual(db.execute('SELECT COUNT(*) FROM inbox').fetchone()[0],0)
    def test_new_sms_keeps_increasing_index_after_emptying(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Path(directory)
            def incoming(ident):sms_store.save(store,dict(event='sms_received',sms_id=ident,number='10010',message='mock',received='now'))
            incoming('first')
            with sms_store.connect(store) as db: previous=db.execute('SELECT MAX(rowid) FROM inbox').fetchone()[0]
            sms_store.archive(store,['first']);sms_store.clear_trash(store);incoming('second')
            with sms_store.connect(store) as db: self.assertGreater(db.execute('SELECT MAX(rowid) FROM inbox').fetchone()[0],previous)
    def test_sent_delete_restore_preserves_send_outcome_and_inbox_same_id(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Path(directory)
            sms_store.save(store,dict(event='sms_received',sms_id='same',number='10010',message='incoming',received='now'))
            for ident in ['same','other','keep']:
                sms_store.sending(store,ident,'10010','outgoing')
                sms_store.outcome(store,ident,'accepted')
            sms_store.archive(store,['same','other'],kind='sent')
            self.assertEqual([r['id'] for r in sms_store.rows(store,'sent')],['keep'])
            self.assertEqual(len(sms_store.rows(store)),1)
            trash=sms_store.rows(store,'trash')
            self.assertEqual({r['source'] for r in trash},{'sent'})
            self.assertEqual({r['state'] for r in trash},{'accepted'})
            sms_store.outcome(store,'same','unknown')
            self.assertEqual(len(sms_store.rows(store,'sent')),1)
            sms_store.archive(store,['same'],restore=True,kind='sent')
            self.assertEqual(next(r for r in sms_store.rows(store,'sent') if r['id']=='same')['state'],'unknown')
            self.assertEqual(sms_store.clear_trash(store),1)
            self.assertEqual(len(sms_store.rows(store,'sent')),2)
            self.assertEqual(len(sms_store.rows(store)),1)
    def test_existing_outbox_migrates_without_losing_history(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            store=Path(directory)
            with sqlite3.connect(store/'inbox.sqlite3') as db:
                db.execute('CREATE TABLE outbox (id TEXT PRIMARY KEY,number TEXT,message TEXT,received TEXT,state TEXT,error TEXT)')
                db.execute("INSERT INTO outbox VALUES ('old','10010','old body','now','accepted','')")
            self.assertEqual(sms_store.rows(store,'sent')[0]['message'],'old body')
            sms_store.archive(store,['old'],kind='sent')
            self.assertEqual(sms_store.rows(store,'sent'),[])
            sms_store.archive(store,['old'],restore=True,kind='sent')
            self.assertEqual(sms_store.rows(store,'sent')[0]['state'],'accepted')
