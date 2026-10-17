import tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
import service

class RouterFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.patches=[patch.object(service,'STORE',root/'store'),patch.object(service,'RUNTIME',root/'run')]
        for p in self.patches:p.start()
        self.server=service.Service()
    def tearDown(self):
        self.server.modem.close()
        for p in self.patches:p.stop()
        self.temp.cleanup()
    def test_firmware_percent_requires_protocol_verification(self):
        self.server.jobs['flash']={'state':'running','action':'install_firmware'}
        def flash(model,confirmation,progress,close):
            progress('正在下载并校验 core.soc');progress('正在写入固件与脚本，请勿断电或拔线')
            self.assertEqual(self.server.jobs['flash']['percent'],70)
            progress('固件写入完成，正在重新验证设备协议')
            self.assertEqual(self.server.jobs['flash']['percent'],95)
        with patch.object(service.firmware,'install',side_effect=flash),patch.object(self.server.modem,'request',return_value={'version':'0.2.4','roamingControlSupported':True}):
            self.server.execute('install_firmware',{'model':'Air780EHV_A11','confirmation':'覆盖固件'},'flash')
        self.assertEqual(self.server.jobs['flash']['percent'],100)
    def test_failed_flash_never_claims_100_percent(self):
        self.server.jobs['flash']={'state':'running','action':'install_firmware'}
        def flash(model,confirmation,progress,close):
            progress('正在写入固件与脚本，请勿断电或拔线');raise RuntimeError('test failure')
        with patch.object(service.firmware,'install',side_effect=flash):
            with self.assertRaises(RuntimeError):self.server.execute('install_firmware',{'model':'Air780EHV_A11','confirmation':'覆盖固件'},'flash')
        self.assertLess(self.server.jobs['flash']['percent'],100)
    def test_tasks_record_submission_and_completion(self):
        with patch.object(service.support_packages,'install',return_value='verified'):
            result=self.server.rpc({'action':'install_support'})
            for _ in range(100):
                with self.server.guard:j=dict(self.server.jobs[result['job']])
                if j['state']=='done':break
                threading.Event().wait(.01)
        self.assertEqual(j['state'],'done');self.assertGreaterEqual(j['completedAt'],j['submittedAt'])
    def public_ip(self,response):
        def once(seconds):self.server.stopping.set()
        with patch.object(service,'run',return_value=response),patch.object(self.server.stopping,'wait',side_effect=once):self.server.public_ip_worker()
        return self.server.public_ip
    def test_public_ip_uses_current_system_egress(self):
        result=self.public_ip('ip=1.1.1.1\nloc=XX\n')
        self.assertEqual(result['address'],'1.1.1.1');self.assertIsInstance(result['checkedAt'],float)
    def test_private_address_is_not_displayed_as_public(self):
        result=self.public_ip('ip=192.168.1.1\n')
        self.assertIsNone(result['address']);self.assertTrue(result['error'])

    def test_wan_probe_is_source_bound_and_preserves_cellular_verification(self):
        import json
        from types import SimpleNamespace
        info={'up':True,'l3_device':'eth0','ipv4-address':[{'address':'192.168.1.2','mask':24}],'route':[{'mask':0,'nexthop':'192.168.1.1'}],'dns-server':['192.168.1.1']}
        def run(args,timeout=15):
            if args[0]=='ubus':return json.dumps(info)
            if args[:3]==['ip','route','get']:return 'via 192.168.1.1 dev eth0 table 1781'
            return ''
        self.server.network_check={'verified':True,'signature':'cellular'}
        def process(args,**kwargs):
            return SimpleNamespace(returncode=0,stdout='Success' if args[0]=='curl' else '',stderr='')
        with patch.object(service,'run',side_effect=run),patch.object(service.subprocess,'run',side_effect=process) as process,patch.object(service,'cellular_dns',return_value='17.253.144.10') as dns,patch.object(service,'discover') as discover:
            self.assertIn('WAN',self.server.verify_network(interface_name='wan'))
        discover.assert_not_called();dns.assert_called_once_with('www.apple.com','192.168.1.2',['192.168.1.1'])
        curl=next(c.args[0] for c in process.call_args_list if c.args[0][0]=='curl')
        self.assertEqual(curl[curl.index('--interface')+1],'192.168.1.2')
        self.assertEqual(self.server.network_check['signature'],'cellular')
