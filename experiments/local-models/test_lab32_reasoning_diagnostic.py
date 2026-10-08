"""Offline checks of the saved diagnostic and its outcome/admission boundary."""
import csv
import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

MEASUREMENTS=pathlib.Path(__file__).resolve().parent/'measurements'
ROOT=MEASUREMENTS/'LAB32-apple-qwen35-9b-reasoning-budget-20261008'
RAW=ROOT/'raw'
spec=importlib.util.spec_from_file_location('finalizer',RAW/'finalize_diagnostic.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ReasoningDiagnostic(unittest.TestCase):
    def test_only_budget_changes_and_followup_keeps_it(self):
        baseline=json.loads((RAW/'baseline-ctx32768-long-request.json').read_text())
        self.assertEqual(baseline['max_tokens'],2048)
        for label,expected in [('control',None),('budget128',128),('budget512',512)]:
            fixture=json.loads((RAW/f'{label}-long-request.json').read_text())
            self.assertEqual(fixture.pop('thinking_budget_tokens',None),expected)
            self.assertEqual(fixture,baseline)
        for path in RAW.glob('*.followup.request.json'):
            request=json.loads(path.read_text())
            expected=128 if 'budget128' in path.name else 512
            self.assertEqual(request['thinking_budget_tokens'],expected)
        self.assertEqual(len(list(RAW.glob('*.followup.request.json'))),16)

    def test_forced_end_does_not_make_dirty_final_successful(self):
        for label,expected in [('control',False),('budget128',True),('budget512',False)]:
            for repeat in ['warmup','r1','r2','r3']:
                prefix=RAW/f'ctx32768-{label}-long-{repeat}'
                final=json.loads(pathlib.Path(str(prefix)+'.final.json').read_text())
                metrics=json.loads(pathlib.Path(str(prefix)+'.metrics.json').read_text())
                self.assertEqual(module.classify_final(final,metrics,'LAB_SENTINEL_42'),expected)
                self.assertEqual(metrics['usage']['prompt_tokens'],28670)
                log=pathlib.Path(str(prefix)+'-server-fragment.txt').read_text()
                forced='reasoning-budget: forced sequence complete, done' in log
                self.assertEqual(forced,label!='control')
                if label=='budget512':
                    self.assertTrue(final['content'].rstrip().endswith('LAB_SENTINEL_42'))
                    self.assertIn('</think>',final['content'])

    def test_regeneration_preserves_failure_and_full_admission_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=pathlib.Path(temporary)/'report'
            shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('__pycache__'))
            result=subprocess.run([sys.executable,str(target/'raw/finalize_diagnostic.py')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            summary=json.loads((target/'raw/diagnostic-summary.json').read_text())
            self.assertEqual(summary['status'],'completed')
            self.assertFalse(summary['full_lab32_admission'])
            self.assertEqual(summary['diagnostic_condition_admission'],{'budget128':True,'budget512':False})
            self.assertEqual(summary['attempts'],{'completed':41,'failed':8,'not-run':0,'planned':0})
            self.assertEqual(summary['case_statistics']['control-long']['measured_repeats'],3)
            self.assertEqual(summary['case_statistics']['control-long']['successful_measured_repeats'],0)
            with (target/'measurements.tsv').open() as f:rows=list(csv.DictReader(f,delimiter='\t'))
            self.assertTrue(all(row['context_tokens']=='32768' for row in rows))
            self.assertTrue(all('budget128' in row['configuration_id'] for row in rows if 'budget128' in row['observation_id']))

    def test_interrupted_finalization_stays_blocked_on_repeated_export(self):
        for initial_status in ['planned','not-run']:
            with self.subTest(initial_status=initial_status), tempfile.TemporaryDirectory() as temporary:
                target=pathlib.Path(temporary)/'report'
                shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('__pycache__'))
                path=target/'manifest.json';manifest=json.loads(path.read_text())
                attempt=next(a for a in manifest['planned_attempts'] if a['id']=='ctx32768-budget512-tool-stream-r3')
                attempt.update(status=initial_status,reason='Synthetic controller interruption')
                path.write_text(json.dumps(manifest))
                snapshots=[]
                for invocation in range(2):
                    result=subprocess.run([sys.executable,str(target/'raw/finalize_diagnostic.py')],capture_output=True,text=True)
                    self.assertEqual(result.returncode,0,result.stderr)
                    summary=json.loads((target/'raw/diagnostic-summary.json').read_text())
                    self.assertEqual(summary['status'],'blocked')
                    self.assertEqual(summary['attempts']['not-run'],1)
                    self.assertEqual(summary['attempts']['planned'],0)
                    self.assertFalse(summary['diagnostic_condition_admission']['budget512'])
                    self.assertEqual(json.loads(path.read_text())['status'],'blocked')
                    snapshots.append({p:p.read_bytes() for p in [path,target/'report.md',target/'measurements.tsv',target/'raw/diagnostic-summary.json',target/'raw/evidence-hashes.json']})
                self.assertEqual(snapshots[0],snapshots[1])

    def test_failure_cannot_be_relabelled_as_success_before_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=pathlib.Path(temporary)/'report'
            shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('__pycache__'))
            path=target/'manifest.json';manifest=json.loads(path.read_text())
            next(a for a in manifest['planned_attempts'] if a['id']=='ctx32768-budget512-long-r1')['status']='completed'
            path.write_text(json.dumps(manifest))
            protected=[path,target/'report.md',target/'measurements.tsv',target/'raw/diagnostic-summary.json']
            before={p:p.read_bytes() for p in protected}
            result=subprocess.run([sys.executable,str(target/'raw/finalize_diagnostic.py')],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(before,{p:p.read_bytes() for p in protected})

    def test_original_blocked_campaign_and_current_hashes_are_preserved(self):
        old=MEASUREMENTS/'LAB32-apple-qwen35-9b-metal-auto-20261007'
        self.assertEqual(json.loads((old/'manifest.json').read_text())['status'],'blocked')
        for directory in [old/'raw',RAW]:
            hashes=json.loads((directory/'evidence-hashes.json').read_text())
            for name,digest in hashes.items():
                self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(),digest,name)


if __name__=='__main__':unittest.main()
