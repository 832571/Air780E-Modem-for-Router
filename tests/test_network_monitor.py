import tempfile,time,unittest,json
from pathlib import Path
from unittest.mock import patch
import service
from network_monitor import TrafficSampler

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.patches=[patch.object(service,'STORE',self.root/'store'),patch.object(service,'RUNTIME',self.root/'run')]
        for item in self.patches:item.start()
        self.server=service.Service();self.server.net_policy['enabled']=True
    def tearDown(self):
        self.server.modem.close()
        for item in self.patches:item.stop()
        self.temp.cleanup()
    def test_settings_persist_and_reject_invalid_without_change(self):
        values={'health_interval':45,'failure_limit':5,'traffic_interval':12,'receiving_number':'+8613800000000','data_roaming':False,**service.dns_settings.DEFAULTS}
        self.server.rpc({'action':'system_settings_save','settings':values})
        restored=service.Service()
        self.assertEqual(restored.rpc({'action':'system_settings'}),values)
        self.assertEqual(restored.health['interval'],45)
        self.assertEqual((self.root/'store/system-settings.json').stat().st_mode&0o777,0o600)
        for bad in [dict(values,traffic_interval=0),dict(values,failure_limit=True),dict(values,health_interval=5.5),{},dict(values,extra=3),dict(values,receiving_number='13800000000'),dict(values,receiving_number='+86\n13800000000')]:
            with self.assertRaises(ValueError):self.server.rpc({'action':'system_settings_save','settings':bad})
            self.assertEqual(self.server.system_settings(),values)

    def test_manual_number_is_captured_only_when_sim_number_missing(self):
        self.server.rpc({'action':'system_settings_save','settings':{'health_interval':30,'failure_limit':3,'traffic_interval':9,'receiving_number':'+8613800000000'}})
        modem=self.server.modem;modem.trusted=True
        with patch.object(service.sms_store,'save') as save:
            modem.accept({'app':service.APP,'protocol':1,'event':'sms_received','sms_id':'test'})
            self.assertEqual(save.call_args.args[1]['receiving_number'],'+8613800000000')
            modem.state['phoneNumber']='+14155550123'
            modem.accept({'app':service.APP,'protocol':1,'event':'sms_received','sms_id':'test2'})
            self.assertEqual(save.call_args.args[1]['receiving_number'],'+14155550123')
        modem.close()
        self.assertIsNone(modem.state['phoneNumber'])

    def test_configurable_threshold_still_verifies_wan(self):
        self.server.rpc({'action':'system_settings_save','settings':{'health_interval':45,'failure_limit':4,'traffic_interval':12}})
        def verify(**kwargs):
            if kwargs.get('interface_name')!='wan':raise RuntimeError('offline')
        with patch.object(self.server.modem,'request'),patch.object(self.server,'execute'),patch.object(self.server,'verify_network',side_effect=verify),patch.object(self.server,'use_wan') as wan:
            self.server.check_health('one');self.server.check_health('two')
            wan.assert_not_called()
            self.server.check_health('three');wan.assert_called_once()
        self.assertEqual(self.server.failure_count,4)

    def test_healthy_checks_do_not_restart_or_failover(self):
        with patch.object(self.server.modem,'request',return_value={'usbEnabled':True}),patch.object(self.server,'verify_network') as verify,patch.object(self.server,'execute') as execute,patch.object(self.server,'use_wan') as wan:
            self.server.check_health('test')
        self.assertEqual(self.server.health['state'],'healthy');verify.assert_called_once();execute.assert_not_called();wan.assert_not_called()
    def test_restart_is_stop_then_start_and_probe_again(self):
        with patch.object(self.server.modem,'request',return_value={'usbEnabled':True}),patch.object(self.server,'verify_network',side_effect=[RuntimeError('failed'),None]),patch.object(self.server,'execute') as execute,patch.object(self.server,'use_wan') as wan:
            self.server.check_health('test')
        self.assertEqual([c.args[0] for c in execute.call_args_list],['stop','start']);wan.assert_not_called();self.assertEqual(self.server.health['state'],'healthy')
    def test_three_failures_verify_wan_before_switch(self):
        def verify(**kwargs):
            if kwargs.get('interface_name')!='wan':raise RuntimeError('offline')
        with patch.object(self.server.modem,'request',return_value={'usbEnabled':True}),patch.object(self.server,'verify_network',side_effect=verify) as probe,patch.object(self.server,'execute') as execute,patch.object(self.server,'use_wan') as wan:
            self.server.check_health('first')
            self.assertEqual(self.server.failure_count,2);wan.assert_not_called()
            self.server.check_health('second')
        wan.assert_called_once();self.assertEqual(self.server.health['state'],'wan')
        self.assertEqual(probe.call_args.kwargs['interface_name'],'wan')
        self.assertEqual(execute.call_count,2)

    def test_wan_probe_only_after_threshold_and_before_route_change(self):
        self.server.failure_count=1;self.server.recovery_attempted=True
        events=[]
        def verify(**kwargs):
            name=kwargs.get('interface_name','air780e');events.append(name)
            if name=='air780e':raise RuntimeError('offline')
        with patch.object(self.server.modem,'request'),patch.object(self.server,'verify_network',side_effect=verify),patch.object(self.server,'use_wan',side_effect=lambda:events.append('switch')):
            self.server.check_health('below')
            self.assertEqual(events,['air780e'])
            self.server.check_health('threshold')
        self.assertEqual(events,['air780e','air780e','wan','switch'])

    def test_manual_stop_during_wan_verification_prevents_switch(self):
        self.server.failure_count=2;self.server.recovery_attempted=True
        def verify(**kwargs):
            if kwargs.get('interface_name')=='wan':self.server.net_policy['enabled']=False
            else:raise RuntimeError('offline')
        with patch.object(self.server.modem,'request'),patch.object(self.server,'verify_network',side_effect=verify),patch.object(self.server,'use_wan') as wan:
            self.server.check_health('threshold');wan.assert_not_called()
        self.assertEqual(self.server.health['state'],'disabled')

    def test_unavailable_wan_does_not_change_routes(self):
        with patch.object(self.server.modem,'request',return_value={'usbEnabled':True}),patch.object(self.server,'verify_network',side_effect=RuntimeError('offline')),patch.object(self.server,'execute'),patch.object(self.server,'use_wan') as wan:
            self.server.check_health('first');self.server.check_health('second')
        wan.assert_not_called();self.assertIn('WAN',self.server.health['detail'])

    def test_health_success_resets_failure_streak(self):
        self.server.failure_count=2;self.server.recovery_attempted=True
        with patch.object(self.server.modem,'request',return_value={'usbEnabled':True}),patch.object(self.server,'verify_network'):
            self.server.check_health('test')
        self.assertEqual(self.server.failure_count,0);self.assertFalse(self.server.recovery_attempted)

    def test_usb_autostart_requires_recognized_protocol_and_respects_stop(self):
        self.server.net_policy['enabled']=None
        with patch.object(service,'discover',return_value={'signature':'usb-new'}),patch.object(self.server.modem,'request',return_value={'usbEnabled':False}) as request:
            self.server.auto_connect();self.server.auto_connect()
        self.assertEqual(self.server.queue.qsize(),1);request.assert_called_once_with('status')
        self.assertIs(self.server.net_policy['enabled'],True)
        self.server.net_policy['enabled']=False;self.server.auto_retry_at=0
        with patch.object(service,'discover') as discover:self.server.auto_connect();discover.assert_not_called()

    def test_incompatible_usb_never_gets_start_command(self):
        with patch.object(service,'discover',return_value={'signature':'other'}),patch.object(self.server.modem,'request',side_effect=RuntimeError('untrusted')):
            self.server.auto_connect()
        self.assertTrue(self.server.queue.empty())

    def test_manual_stop_cancels_recovery_before_start(self):
        def stop(*args):self.server.net_policy['enabled']=False
        with patch.object(self.server.modem,'request',return_value={'usbEnabled':True}),patch.object(self.server,'verify_network',side_effect=RuntimeError('offline')),patch.object(self.server,'execute',side_effect=stop) as execute,patch.object(self.server,'use_wan') as wan:
            self.server.check_health('test')
        self.assertEqual(execute.call_count,1);wan.assert_not_called()
    def test_fallback_keeps_checking_without_repeated_restarts(self):
        self.server.net_policy['fallback']=True
        with patch.object(self.server.modem,'request',return_value={'usbEnabled':True}),patch.object(self.server,'verify_network',side_effect=RuntimeError('offline')),patch.object(self.server,'execute') as execute:
            self.server.check_health('test')
        execute.assert_not_called();self.assertEqual(self.server.health['state'],'wan')
    def test_unknown_disconnected_device_is_not_automatically_started(self):
        self.server.net_policy['enabled']=None
        with patch.object(self.server.modem,'request',side_effect=RuntimeError('disconnected')),patch.object(self.server,'execute') as execute:
            self.server.check_health('test')
        execute.assert_not_called()
    def test_manual_stop_persists_across_service_restart(self):
        self.server.rpc({'action':'stop'})
        restarted=service.Service()
        try:
            self.assertIs(restarted.net_policy['enabled'],False)
            with patch.object(restarted.modem,'request') as request:restarted.check_health('test')
            request.assert_not_called()
        finally:restarted.modem.close()

class TrafficTests(unittest.TestCase):
    def test_rates_totals_and_counter_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);node=root/'eth2';(node/'statistics').mkdir(parents=True);(node/'ifindex').write_text('20')
            def counters(tx,rx):
                for k,v in dict(tx_bytes=tx,rx_bytes=rx,tx_packets=tx//10,rx_packets=rx//10).items():(node/'statistics'/k).write_text(str(v))
            sampler=TrafficSampler(root);counters(100,200)
            with patch('network_monitor.time.monotonic',return_value=10):sampler.sample('eth2')
            counters(190,380)
            with patch('network_monitor.time.monotonic',return_value=19):sampler.sample('eth2')
            self.assertEqual(sampler.latest['uploadBps'],10);self.assertEqual(sampler.latest['downloadBps'],20);self.assertEqual(sampler.latest['tx_packets'],19)
            counters(10,20)
            with patch('network_monitor.time.monotonic',return_value=28):sampler.sample('eth2')
            self.assertEqual(sampler.latest['uploadBps'],0);self.assertEqual(sampler.latest['rx_bytes'],20)
            sampler.sample(None);self.assertFalse(sampler.latest['available'])
