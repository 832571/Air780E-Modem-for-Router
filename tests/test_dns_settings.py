import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import dns_settings,service

class DNSTests(unittest.TestCase):
    def test_validate_defaults_and_reject_injection(self):
        self.assertEqual(dns_settings.validate({}),dns_settings.DEFAULTS)
        for value in ['example.com','1.1.1.1; reboot','::1','0.0.0.0','127.0.0.1','224.0.0.1',None]:
            with self.assertRaises(ValueError):dns_settings.validate({'dns_primary':value})
    def test_persistent_forwarder_and_cellular_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=root/'config';config.mkdir()
            for name in ['dhcp','network']:(config/name).write_text('original')
            def query(args,**kwargs):return Mock(stdout='interface' if args[-1]=='network.air780e' else '')
            run=Mock()
            with patch.object(dns_settings.subprocess,'run',side_effect=query):dns_settings.apply({},run,root,config)
            commands=[c.args[0] for c in run.call_args_list]
            self.assertIn(['uci','set','dhcp.@dnsmasq[0].noresolv=1'],commands)
            self.assertIn(['uci','set','network.air780e.peerdns=0'],commands)
            for address in ['1.1.1.1','9.9.9.9']:
                self.assertIn(['uci','add_list','network.air780e.dns='+address],commands)
            self.assertEqual(commands[-1],['/etc/init.d/dnsmasq','restart'])
    def test_apply_failure_restores_original_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=root/'config';config.mkdir()
            for name in ['dhcp','network']:(config/name).write_text('original-'+name)
            def fail(args):
                (config/'dhcp').write_text('changed');raise RuntimeError('failed')
            with patch.object(dns_settings.subprocess,'run',return_value=Mock(stdout='')),self.assertRaises(RuntimeError):
                dns_settings.apply({},fail,root,config)
            self.assertEqual((config/'dhcp').read_text(),'original-dhcp')
    def test_old_settings_migrate_and_failed_save_does_not_claim_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch.object(service,'STORE',root/'store'),patch.object(service,'RUNTIME',root/'run'):
                server=service.Service();old=server.system_settings()
                new=dict(old,dns_primary='8.8.8.8')
                with patch.object(server,'apply_dns',side_effect=RuntimeError('apply failed')),self.assertRaises(RuntimeError):
                    server.rpc({'action':'system_settings_save','settings':new})
                self.assertEqual(server.system_settings(),old)
                with patch.object(server,'apply_dns') as apply:
                    server.rpc({'action':'system_settings_save','settings':new});apply.assert_called_once_with(new)
                self.assertEqual(service.Service().system_settings()['dns_primary'],'8.8.8.8')
