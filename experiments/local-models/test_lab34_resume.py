"""Offline replay checks for the registered continuation; no GPU process starts."""
import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=pathlib.Path(__file__).resolve().parent/'measurements/LAB34-apple-load-resume-20261009'
spec=importlib.util.spec_from_file_location('lab34_resume',ROOT/'raw/run_load.py')
module=importlib.util.module_from_spec(spec)
resources_spec=importlib.util.spec_from_file_location('resources',ROOT/'raw/resources.py')
resources=importlib.util.module_from_spec(resources_spec);resources_spec.loader.exec_module(resources)
with patch.dict(sys.modules,resources=resources):spec.loader.exec_module(module)

class ResumeAudit(unittest.TestCase):
    def replay(self,changed=False):
        with tempfile.TemporaryDirectory() as temporary:
            target=pathlib.Path(temporary)/'report';shutil.copytree(ROOT,target)
            manifest=json.loads((target/'manifest.json').read_text())
            for attempt in manifest['planned_attempts']:
                attempt.update(status='planned',reason=None,evidence_files=[])
            (target/'manifest.json').write_text(json.dumps(manifest))
            if changed:
                path=target/'raw/prior-short/r1-c2/request-0001.response.bin'
                path.write_bytes(path.read_bytes()+b' ')
            campaign=Mock();campaign.guard=None;campaign.startup.side_effect=RuntimeError('Synthetic no-GPU stop')
            with patch.object(module,'RAW',target/'raw'),patch.object(module,'MANIFEST',target/'manifest.json'),patch.object(module,'Campaign',return_value=campaign):
                module.main()
            updated=json.loads((target/'manifest.json').read_text())
            return campaign,updated

    def test_changed_historical_bytes_stop_before_native_start(self):
        campaign,manifest=self.replay(changed=True)
        campaign.startup.assert_not_called()
        audit=next(a for a in manifest['planned_attempts'] if a['id']=='prior-evidence-audit')
        self.assertEqual(audit['status'],'failed')

    def test_valid_historical_audit_is_distinct_from_new_measurements(self):
        campaign,manifest=self.replay()
        campaign.startup.assert_called_once_with()
        self.assertEqual(manifest['planned_attempts'][0]['status'],'completed')
        self.assertEqual(manifest['planned_attempts'][0]['kind'],'exercise')
        self.assertEqual(manifest['planned_attempts'][1]['status'],'failed')
        self.assertEqual(module.ORDER,[(2,4),(2,1),(3,4),(3,1),(3,2)])

if __name__=='__main__':unittest.main()
