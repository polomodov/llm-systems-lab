"""Offline checks of actual recovery evidence and the fixed-budget admission."""
import csv
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parent/'measurements/LAB32-apple-qwen35-9b-32k-recovery-20261008'
RAW=ROOT/'raw'
spec=importlib.util.spec_from_file_location('budget_finalizer',RAW/'finalize_campaign.py')
finalizer=importlib.util.module_from_spec(spec);spec.loader.exec_module(finalizer)


def copied_report(temporary):
    target=pathlib.Path(temporary)/'report'
    shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('__pycache__'))
    return target


def run_finalizer(target):
    return subprocess.run([sys.executable,str(target/'raw/finalize_campaign.py')],capture_output=True,text=True)


class ScopedBudgetAdmission(unittest.TestCase):
    def test_regeneration_admits_only_scoped32k_with_recovery_and_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=copied_report(temporary);result=run_finalizer(target)
            self.assertEqual(result.returncode,0,result.stderr)
            manifest=json.loads((target/'manifest.json').read_text())
            summary=json.loads((target/'raw/campaign-summary.json').read_text())
            self.assertEqual(manifest['status'],'completed')
            self.assertEqual(summary['admitted_contexts'],[32768])
            self.assertFalse(summary['full_lab32_admission'])
            self.assertEqual(summary['thinking_budget_tokens'],128)
            self.assertEqual(summary['cancel_release_timeout_seconds'],60)
            self.assertEqual(summary['attempts'],{'completed':28,'failed':0,'not-run':0,'planned':0})
            for ctx in [32768]:
                with (target/'measurements.tsv').open() as stream:
                    rows=[r for r in csv.DictReader(stream,delimiter='\t') if r['observation_id'].startswith(f'ctx{ctx}-')]
                self.assertTrue(rows)
                self.assertTrue(all(r['context_tokens']==str(ctx) and 'budget128' in r['configuration_id'] for r in rows))

    def test_scoped32k_cannot_erase_the_sequential16k_failure(self):
        sequential=ROOT.parent/'LAB32-apple-qwen35-9b-metal-budget128-20261008'
        manifest=json.loads((sequential/'manifest.json').read_text())
        self.assertEqual(manifest['status'],'blocked')
        failed=next(a for a in manifest['planned_attempts'] if a['id']=='ctx16384-long-warmup')
        self.assertEqual(failed['status'],'failed')
        final=json.loads((sequential/'raw/ctx16384-long-warmup.final.json').read_text())
        self.assertEqual(final['content'],'LAB_SENTINEL_42.')
        self.assertTrue(all(a['status']=='not-run' for a in manifest['planned_attempts'] if a['id'].startswith('ctx32768-')))

    def assert_rejected_without_export(self,target):
        protected=[target/'manifest.json',target/'report.md',target/'measurements.tsv',target/'raw/campaign-summary.json',target/'raw/evidence-hashes.json']
        before={p:p.read_bytes() for p in protected}
        result=run_finalizer(target)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(before,{p:p.read_bytes() for p in protected})

    def test_cancel_for_another_task_is_not_accepted_by_a_true_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=copied_report(temporary);path=target/'raw/ctx32768-cancel-execution.json'
            data=json.loads(path.read_text());self.assertTrue(data['accepted'])
            data['canceled_task_ids']=['999999999999999999'];path.write_text(json.dumps(data))
            self.assert_rejected_without_export(target)

    def test_release_duration_cannot_disagree_with_the_client_exit_timeline(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=copied_report(temporary);path=target/'raw/ctx32768-cancel-execution.json'
            data=json.loads(path.read_text());data['release_after_client_s']=0.0;path.write_text(json.dumps(data))
            self.assert_rejected_without_export(target)

    def test_invalid_primary_tool_contract_is_rejected_before_any_export(self):
        mutations={
            'name':lambda calls:calls[0]['function'].update(name='execute_shell'),
            'arguments':lambda calls:calls[0]['function'].update(arguments='{"key":"beta"}'),
            'extra_argument':lambda calls:calls[0]['function'].update(arguments='{"key":"alpha","command":"id"}'),
            'invalid_json':lambda calls:calls[0]['function'].update(arguments='{'),
            'missing_id':lambda calls:calls[0].pop('id'),
            'empty_id':lambda calls:calls[0].update(id=''),
            'blank_id':lambda calls:calls[0].update(id='   '),
            'wrong_type':lambda calls:calls[0].update(type='shell'),
            'multiple_calls':lambda calls:calls.append(dict(calls[0])),
        }
        for kind in ['tool','tool-stream']:
            for label,mutate in mutations.items():
                with self.subTest(kind=kind,mutation=label), tempfile.TemporaryDirectory() as temporary:
                    target=copied_report(temporary)
                    suffix='.assembled.json' if kind=='tool-stream' else '.response.json'
                    path=target/f'raw/ctx32768-{kind}-r1{suffix}'
                    data=json.loads(path.read_text())
                    message=data if kind=='tool-stream' else data['choices'][0]['message']
                    mutate(message['tool_calls']);path.write_text(json.dumps(data))
                    self.assert_rejected_without_export(target)

    def test_tool_result_must_match_primary_call_and_registered_value(self):
        for kind in ['tool','tool-stream']:
            for field,value in [('tool_call_id','another-call'),('content','UNREGISTERED_VALUE'),('role','user')]:
                with self.subTest(kind=kind,field=field), tempfile.TemporaryDirectory() as temporary:
                    target=copied_report(temporary)
                    path=target/f'raw/ctx32768-{kind}-r1.followup.request.json'
                    data=json.loads(path.read_text());data['messages'][-1][field]=value
                    path.write_text(json.dumps(data));self.assert_rejected_without_export(target)
            with self.subTest(kind=kind,field='assistant-call'), tempfile.TemporaryDirectory() as temporary:
                target=copied_report(temporary)
                path=target/f'raw/ctx32768-{kind}-r1.followup.request.json'
                data=json.loads(path.read_text());data['messages'][-2]['tool_calls'][0]['function']['name']='execute_shell'
                path.write_text(json.dumps(data));self.assert_rejected_without_export(target)

    def test_sequential_campaign_uses_the_same_tool_verifier(self):
        sequential=ROOT.parent/'LAB32-apple-qwen35-9b-metal-budget128-20261008'
        spec=importlib.util.spec_from_file_location('sequential_finalizer',sequential/'raw/finalize_campaign.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.verify_tool_round_trip.__code__.co_code,finalizer.verify_tool_round_trip.__code__.co_code)
        for kind in ['tool','tool-stream']:
            module.verify_protocol(sequential/'raw',f'ctx8192-{kind}-r1')

    def test_missing_budget_in_tool_followup_prevents_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=copied_report(temporary);path=target/'raw/ctx32768-tool-stream-r1.followup.request.json'
            data=json.loads(path.read_text());del data['thinking_budget_tokens'];path.write_text(json.dumps(data))
            self.assert_rejected_without_export(target)

    def test_missing_recovery_prevents_admission_even_if_attempt_completed(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=copied_report(temporary)
            (target/'raw/ctx32768-overflow-recovery-execution.json').unlink()
            self.assert_rejected_without_export(target)

    def test_unobserved_release_is_unavailable_instead_of_a_fabricated_zero(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);raw=root/'raw';raw.mkdir()
            case='ctx32768-cancel';attempts={case:dict(configuration_id='metal-ctx32768-budget128-cancel')}
            (raw/(case+'-execution.json')).write_text(json.dumps({'release_after_client_s':None,'exit_code':28}))
            finalizer.export_measurements(raw,root,attempts)
            with (root/'measurements.tsv').open() as stream:rows=list(csv.DictReader(stream,delimiter='\t'))
            row=next(r for r in rows if r['metric']=='slot_release_after_disconnect')
            self.assertEqual(row['value'],'')
            self.assertEqual(row['status'],'unavailable')
            self.assertTrue(row['unavailable_reason'])


if __name__=='__main__':unittest.main()
