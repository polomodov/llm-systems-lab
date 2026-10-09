"""Offline regression of the interrupted matrix and source tampering."""
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parent/'measurements/LAB34-apple-load-complete-20261008'
spec=importlib.util.spec_from_file_location('complete_export',ROOT/'raw/finalize_complete.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class CompleteExport(unittest.TestCase):
    def copied(self,temporary):
        target=pathlib.Path(temporary)/'report'
        shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('__pycache__'))
        return target

    def test_repeated_export_keeps_sigkill_and_omissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=self.copied(temporary);snapshots=[]
            for _ in range(2):
                result=subprocess.run([sys.executable,'-B',str(target/'raw/finalize_complete.py')],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                summary=json.loads((target/'raw/summary.json').read_text())
                self.assertEqual(summary['status'],'blocked')
                self.assertEqual(summary['attempts'],{'completed':6,'failed':2,'not-run':5})
                self.assertIsNone(summary['sustained'])
                self.assertEqual(summary['shutdown']['returncode'],-9)
                self.assertEqual(summary['shutdown']['interrupts'],[])
                self.assertEqual(summary['blocks']['r2-c4']['failed'],2)
                snapshots.append({p:p.read_bytes() for p in [target/'manifest.json',target/'measurements.tsv',target/'raw/summary.json',target/'raw/evidence-sha256.json']})
            self.assertEqual(snapshots[0],snapshots[1])

    def test_changed_primary_usage_is_rejected_before_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=self.copied(temporary)
            path=target/'raw/r1-c2/request-0001.response.bin'
            data=json.loads(path.read_bytes());data['usage']['completion_tokens']-=1
            body=json.dumps(data).encode();path.write_bytes(body)
            # Keep size metadata coherent, so the semantic usage check must reject it.
            record_path=target/'raw/r1-c2/request-0001.json'
            record=json.loads(record_path.read_text());record['response_bytes']=len(body)
            record_path.write_text(json.dumps(record))
            summary_path=target/'raw/r1-c2/summary.json'
            summary=json.loads(summary_path.read_text());summary['results'][0]=record
            summary_path.write_text(json.dumps(summary))
            protected=[target/'manifest.json',target/'measurements.tsv',target/'raw/summary.json',target/'raw/evidence-sha256.json']
            before={p:p.read_bytes() for p in protected}
            result=subprocess.run([sys.executable,'-B',str(target/'raw/finalize_complete.py')],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(before,{p:p.read_bytes() for p in protected})


if __name__=='__main__':unittest.main()
