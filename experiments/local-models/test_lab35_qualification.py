"""Offline LAB35 checks: shared driver path and immutable input admission."""
import importlib.util,json,pathlib,shutil,sys,tempfile,unittest
from unittest.mock import Mock,patch
ROOT=pathlib.Path(__file__).resolve().parent/'measurements/LAB35-apple-qualification-retry-20261009'
raw=ROOT/'raw'
rs=importlib.util.spec_from_file_location('resources',raw/'resources.py');resources=importlib.util.module_from_spec(rs);rs.loader.exec_module(resources)
spec=importlib.util.spec_from_file_location('lab35_qualification',raw/'run_qualification.py');module=importlib.util.module_from_spec(spec)
with patch.dict(sys.modules,resources=resources):spec.loader.exec_module(module)

class Qualification(unittest.TestCase):
    def test_nested_variant_uses_existing_shared_driver(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=pathlib.Path(temporary);(target/'chat-r1').mkdir();(target/'chat-r1/summary.json').write_text('{"failed":0,"success_latency_p95_seconds":1}')
            campaign=module.Campaign();campaign.ensure=Mock();client=Mock(pid=123456);client.wait.return_value=0
            with patch.object(module,'RAW',target),patch.object(module,'ROOT',ROOT),patch.object(module,'REQUEST','chat-request.json'),patch.object(module,'api',return_value=[{'is_processing':False}]),patch.object(module,'write'),patch.object(module.subprocess,'Popen',return_value=client) as start:
                _,accepted=campaign.block('chat-r1',1,1)
            self.assertTrue(accepted)
            command=start.call_args.args[0]
            self.assertEqual(pathlib.Path(command[2]),ROOT/'raw/concurrency_driver.py')
            self.assertTrue(pathlib.Path(command[2]).is_file())
            self.assertEqual(command[command.index('--request')+1],str(target/'chat-request.json'))
            self.assertEqual(command[command.index('--requests')+1],'1')

    def test_changed_input_stops_before_any_native_campaign(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=pathlib.Path(temporary)/'raw';shutil.copytree(raw,target)
            p=target/'chat-request.json';p.write_bytes(p.read_bytes()+b' ')
            with patch.object(module,'RAW',target),patch.object(module,'Campaign') as start:
                with self.assertRaises(AssertionError):module.main()
            start.assert_not_called()

if __name__=='__main__':unittest.main()
