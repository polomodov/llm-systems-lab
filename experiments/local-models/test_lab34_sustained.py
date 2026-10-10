"""Offline controller regressions: failed blocks and interrupt cleanup."""
import importlib.util
import json
import pathlib
import shutil
import signal
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

ROOT=pathlib.Path(__file__).resolve().parent/'measurements/LAB34-apple-sustained-resume-20261009'
raw=ROOT/'raw'
rspec=importlib.util.spec_from_file_location('resources',raw/'resources.py')
resources=importlib.util.module_from_spec(rspec);rspec.loader.exec_module(resources)
spec=importlib.util.spec_from_file_location('sustained_controller',raw/'run_sustained.py')
module=importlib.util.module_from_spec(spec)
with patch.dict(sys.modules,resources=resources):spec.loader.exec_module(module)

class SustainedController(unittest.TestCase):
    def test_failed_primary_block_is_registered_before_native_exit_propagates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)/'report';shutil.copytree(ROOT,root)
            raw=root/'raw'
            shutil.rmtree(raw/'sustained',ignore_errors=True)
            m=json.loads((root/'manifest.json').read_text())
            for attempt in m['planned_attempts']:attempt.update(status='planned',reason=None,evidence_files=[])
            (root/'manifest.json').write_text(json.dumps(m))
            campaign=Mock();campaign.guard=None
            def startup():
                (raw/'startup-execution.json').write_text('{"synthetic":true}')
                module.result('startup',True)
            def block(name,concurrency,requests=12):
                if name=='warmup':
                    (raw/'warmup-execution.json').write_text('{"synthetic":true}')
                    return {'requests':2},True
                (raw/name).mkdir()
                (raw/name/'summary.json').write_text('{"requests":12,"synthetic":true}')
                raise RuntimeError('Synthetic native exit after primary block')
            campaign.startup.side_effect=startup;campaign.block.side_effect=block
            audit=types.SimpleNamespace(validate_block=lambda name:(json.loads((raw/name/'summary.json').read_text()),[]))
            with patch.object(module,'RAW',raw),patch.object(module,'MANIFEST',root/'manifest.json'),patch.object(module,'Campaign',return_value=campaign),patch.dict(sys.modules,finalize_sustained=audit):
                module.main()
            series=json.loads((raw/'sustained/series.json').read_text())
            self.assertEqual(series['status'],'failed')
            self.assertEqual(series['blocks'][0]['directory'],'sustained/block-0001')
            self.assertFalse(series['blocks'][0]['accepted'])
            campaign.shutdown.assert_called_once_with()

    def test_keyboard_interrupt_terminates_only_the_owned_http_client(self):
        campaign=module.Campaign();campaign.process=Mock();campaign.process.poll.return_value=None
        client=Mock(pid=123456);client.poll.return_value=None;client.wait.side_effect=[KeyboardInterrupt(),0]
        with tempfile.TemporaryDirectory() as temporary,patch.object(module,'RAW',pathlib.Path(temporary)),patch.object(module,'api',return_value=[{'is_processing':False}]),patch.object(module.subprocess,'Popen',return_value=client),patch.object(module.os,'killpg') as kill:
            with self.assertRaises(KeyboardInterrupt):campaign.block('synthetic',1)
        kill.assert_called_once_with(123456,signal.SIGTERM)
        self.assertIsNone(campaign.client)

if __name__=='__main__':unittest.main()
