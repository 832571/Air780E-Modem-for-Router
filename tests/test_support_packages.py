import subprocess
import unittest
from unittest.mock import Mock, patch
import support_packages as support

class SupportPackagesTests(unittest.TestCase):
    def result(self, code=0, text=''):
        return subprocess.CompletedProcess([], code, text, '')

    @patch.object(support, 'command')
    def test_installed_verifies_without_network_install(self, command):
        command.side_effect=[self.result(text='Status: install user installed\n'),self.result()]
        self.assertIn('Unicode',support.install(Mock()))
        self.assertEqual(command.call_count,2)
        self.assertEqual(command.call_args_list[1].args[0][1],'-c')

    @patch.object(support, 'command')
    def test_missing_installs_fixed_package_and_verifies(self, command):
        command.side_effect=[self.result(1),self.result(),self.result()]
        support.install(Mock())
        self.assertEqual(command.call_args_list[1].args[0],['opkg','install','python3-codecs'])

    @patch.object(support, 'command')
    def test_unrelated_update_failure_still_attempts_install(self, command):
        command.side_effect=[self.result(1),self.result(1),self.result(1),self.result(),self.result()]
        support.install(Mock())
        self.assertEqual(command.call_args_list[2].args[0],['opkg','update'])
        self.assertEqual(command.call_count,5)

    @patch.object(support, 'command')
    def test_install_failure_does_not_claim_success(self, command):
        command.side_effect=[self.result(1)]*4
        with self.assertRaisesRegex(RuntimeError,'安装失败'):support.install(Mock())

    @patch.object(support, 'command')
    def test_codec_failure_does_not_claim_success(self, command):
        command.side_effect=[self.result(text='Status: install ok installed\n'),self.result(1)]
        with self.assertRaisesRegex(RuntimeError,'验证失败'):support.install(Mock())

    @patch.object(support.subprocess,'run',side_effect=subprocess.TimeoutExpired('opkg',180))
    def test_timeout_has_actionable_message(self, run):
        with self.assertRaisesRegex(RuntimeError,'超时'):support.command(['opkg','install','python3-codecs'],180)

class SupportJobTests(unittest.TestCase):
    def test_install_runs_without_modem_worker_and_deduplicates(self):
        import service,tempfile,threading,time
        from pathlib import Path
        started=threading.Event();release=threading.Event();finished=threading.Event()
        def install(progress):
            started.set();release.wait(3);finished.set();return 'verified'
        with tempfile.TemporaryDirectory() as directory,patch.object(service,'STORE',Path(directory)/'store'),patch.object(service,'RUNTIME',Path(directory)/'run'),patch.object(service.support_packages,'install',side_effect=install) as installer:
            server=service.Service()
            try:
                first=server.rpc({'action':'install_support','client_id':'support-first'})
                self.assertTrue(started.wait(2))
                second=server.rpc({'action':'install_support','client_id':'support-second'})
                self.assertEqual(first,second)
                self.assertTrue(server.queue.empty())
                release.set();self.assertTrue(finished.wait(2))
                for _ in range(100):
                    with server.guard:done=server.jobs[first['job']]['state']=='done'
                    if done:break
                    time.sleep(.01)
                self.assertTrue(done);installer.assert_called_once()
            finally:release.set();server.modem.close()
