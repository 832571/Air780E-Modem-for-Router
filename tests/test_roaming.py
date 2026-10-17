import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import service
class RoamingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.patches=[patch.object(service,'STORE',self.root/'store'),patch.object(service,'RUNTIME',self.root/'run')]
  for p in self.patches:p.start()
  self.server=service.Service()
 def tearDown(self):
  for p in self.patches:p.stop()
  self.temp.cleanup()
 def test_default_off_legacy_firmware_rejected(self):
  self.assertFalse(self.server.system_settings()['data_roaming'])
  with self.assertRaises(ValueError):self.server.rpc({'action':'system_settings_save','settings':dict(self.server.system_settings(),data_roaming=True)})
 def test_only_module_ack_persists_true(self):
  self.server.modem.state.update(connected=True,roamingControlSupported=True)
  out=self.server.rpc({'action':'system_settings_save','settings':dict(self.server.system_settings(),data_roaming=True)})
  self.assertTrue(out['roamingPending']);self.assertFalse(self.server.system_settings()['data_roaming'])
  with patch.object(self.server.modem,'request',side_effect=[{'roamingControlSupported':True},{'dataRoamingAllowed':True}]):self.server.execute('set_roaming',{'enabled':True},'test')
  self.assertTrue(service.Service().system_settings()['data_roaming'])
 def test_missing_ack_never_enables(self):
  with patch.object(self.server.modem,'request',side_effect=[{'roamingControlSupported':True},{}]),self.assertRaises(RuntimeError):self.server.execute('set_roaming',{'enabled':True},'test')
  self.assertFalse(self.server.system_settings()['data_roaming'])
 def test_blocked_roaming_does_not_restart_data(self):
  self.server.net_policy['enabled']=True
  with patch.object(self.server.modem,'request',return_value={'roamingControlSupported':True,'roamingBlocked':True}),patch.object(self.server,'verify_network') as verify,patch.object(self.server,'execute') as execute:
   self.server.check_health('test');verify.assert_not_called();execute.assert_not_called()
 def test_reject_non_boolean(self):
  for v in [1,'true',None]:
   with self.assertRaises(ValueError):self.server.validate_settings(dict(self.server.system_settings(),data_roaming=v))

 def test_manual_stop_commands_module_even_if_roaming_already_disabled_usb(self):
  responses=[{'usbEnabled':False,'usbRequested':True},{},{'event':'network'},{'usbEnabled':False,'usbRequested':False}]
  with patch.object(self.server.modem,'request',side_effect=responses) as request,patch.object(service.time,'sleep'),patch.object(service.subprocess,'run'):
   self.server.execute('stop',{},'test')
  self.assertIn('stop',[c.args[0] for c in request.call_args_list])
  self.assertFalse(self.server.net_policy['enabled'])

 def test_pending_policy_rejects_overlapping_save(self):
  self.server.modem.state.update(connected=True,roamingControlSupported=True)
  self.server.rpc({'action':'system_settings_save','settings':dict(self.server.system_settings(),data_roaming=True)})
  with self.assertRaises(ValueError):self.server.rpc({'action':'system_settings_save','settings':self.server.system_settings()})
  self.assertEqual(self.server.queue.qsize(),1)
