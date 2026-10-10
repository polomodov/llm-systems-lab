"""Retain the power stop and count historical evidence only once."""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parent/'measurements/LAB34-apple-load-resume-20261009'

class ResumeExport(unittest.TestCase):
    def test_power_stop_and_history_survive_idempotent_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=pathlib.Path(temporary)/'report';shutil.copytree(ROOT,target)
            snapshots=[]
            for _ in range(2):
                result=subprocess.run([sys.executable,'-B',str(target/'raw/finalize_resume.py')],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                summary=json.loads((target/'raw/summary.json').read_text())
                self.assertEqual(summary['status'],'blocked')
                self.assertEqual(summary['attempts'],{'completed':3,'failed':2,'not-run':5})
                self.assertIsNone(summary['sustained'])
                self.assertEqual(summary['shutdown']['returncode'],0)
                self.assertEqual(len(summary['shutdown']['interrupts']),1)
                self.assertEqual(summary['shutdown']['guard_reason'],'Memory/power admission failed')
                self.assertEqual(summary['provenance']['new_requests'],14)
                self.assertEqual(summary['provenance']['all_started_requests'],76)
                self.assertEqual(summary['provenance']['all_failed_requests'],3)
                snapshots.append({name:(target/name).read_bytes() for name in ['manifest.json','measurements.tsv','raw/summary.json','raw/evidence-sha256.json']})
            self.assertEqual(*snapshots)

    def test_historical_copy_tampering_prevents_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=pathlib.Path(temporary)/'report';shutil.copytree(ROOT,target)
            p=target/'raw/prior-short/r1-c4/request-0001.response.bin';p.write_bytes(p.read_bytes()+b' ')
            names=['manifest.json','measurements.tsv','raw/summary.json','raw/evidence-sha256.json']
            before={name:(target/name).read_bytes() for name in names}
            result=subprocess.run([sys.executable,'-B',str(target/'raw/finalize_resume.py')],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(before,{name:(target/name).read_bytes() for name in names})

if __name__=='__main__':unittest.main()
