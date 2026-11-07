"""Synthetic provider/native documents only; never contact an API or read .env."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from common import read, sha, write
import hn_o01 as capture
import hn_o01_billing as billing

NOW = '2026-11-07T10:00:00Z'
MODEL = 'gpt-6.1-sol'


def fixture(root, *, offline=False):
    bundle = root / 'bundle'; collection = bundle / 'trace/collection'; raw = collection / 'trial'
    sessions = raw / 'agent/sessions'; sessions.mkdir(parents=True)
    payloads = [('session_meta', {'id': 'thread-1', 'cli_version': '0.167.0', 'source': 'exec', 'thread_source': 'user'}),
        ('event_msg', {'type': 'task_started'}),
        ('turn_context', {'model': MODEL, 'approval_policy': 'never'}),
        ('response_item', {'type': 'custom_tool_call', 'call_id': 'tool-1'}),
        ('token_usage_record', {'thread_id': 'thread-1', 'response_id': 'resp-1', 'usage': {'input_tokens': 100, 'output_tokens': 20}}),
        ('event_msg', {'type': 'task_complete'})]
    def rollout(rows):
        (sessions / 'rollout.jsonl').write_text(''.join(json.dumps({'timestamp': NOW, 'ordinal': i, 'type': kind, 'payload': value}) + '\n' for i, (kind, value) in enumerate(rows)))
    rollout(payloads)
    (raw / 'agent/codex.txt').write_text('\n'.join([json.dumps({'type': 'thread.started', 'thread_id': 'thread-1'}),
        json.dumps({'type': 'turn.started'}),
        NOW + ' INFO codex_core::session: server reported model ' + MODEL + ' (matches requested model)',
        NOW + ' TRACE codex_api::sse::responses: SSE event: ' + json.dumps({'type': 'response.completed',
            'response': {'id': 'resp-1', 'model': MODEL, 'status': 'completed', 'usage': {'input_tokens': 100, 'output_tokens': 20}}}),
        json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 100, 'output_tokens': 20}})]) + '\n')
    write(raw / 'result.json', {'agent_execution': {'started_at': NOW, 'finished_at': '2026-11-07T10:00:02Z'},
                              'agent_info': {'model_info': {'name': MODEL}}})
    record = {'run_id': '2026-11-07-fixture-hn-o01', 'model': {'id': MODEL},
              'inputs': {'manifest_sha256': 'a' * 64}, 'loop': {'budget_usd': 2}}
    write(bundle / 'trace/start-receipt.json', {'started_at': NOW})
    write(bundle / 'trace/execution-claim.json', {'permit': {'billing_project': 'proj-fixture', 'billing_api_key_id': 'key-fixture'}})
    write(collection / 'controller.json', {'finished_at': '2026-11-07T10:00:03Z'})
    report = capture.collect(collection, 'trial', record, offline=offline)
    seal = {'run_id': record['run_id'], 'offline': offline, 'files': capture.inventory(collection)}
    write(bundle / 'trace/collection-seal.json', seal)
    start = 1794009600
    usage = {'object': 'organization.usage.completions.result', 'project_id': 'proj-fixture',
             'api_key_id': 'key-fixture', 'model': MODEL, 'input_tokens': 100, 'output_tokens': 20, 'num_model_requests': 1}
    cost = {'object': 'organization.costs.result', 'project_id': 'proj-fixture', 'api_key_id': 'key-fixture',
            'line_item': MODEL + ', input_tokens', 'amount': {'value': 0.001, 'currency': 'usd'}}
    def page(row):
        return [{'object': 'page', 'data': [{'object': 'bucket', 'start_time': start, 'end_time': start + 86400, 'results': [row]}], 'has_more': False, 'next_page': None}]
    query = {'start_time': start, 'end_time': start + 86400, 'project_ids': ['proj-fixture'], 'api_key_ids': ['key-fixture'],
             'usage_group_by': ['project_id', 'api_key_id', 'model'], 'cost_group_by': ['project_id', 'api_key_id', 'line_item']}
    export = {'kind': 'hn-o01-provider-billing-export-v1', 'synthetic': False, 'run_id': record['run_id'],
              'collection_seal_sha256': sha(bundle / 'trace/collection-seal.json'), 'inputs_sha256': 'a' * 64,
              'response_set_sha256': report['response_set_sha256'],
              'scope': {'project_id': 'proj-fixture', 'api_key_id': 'key-fixture', 'start_time': start, 'end_time': start + 86400,
                        'exclusive_for_entire_bucket': True, 'other_activity': False},
              'review': {'status': 'settled', 'reviewer': 'fixture-only-operator', 'basis': 'Invented values exercise validation only',
                         'all_retries_included': True, 'reviewed_at': '2026-11-08T12:00:00Z'},
              'snapshots': [{'retrieved_at': time, 'query': deepcopy(query), 'usage_pages': page(deepcopy(usage)), 'cost_pages': page(deepcopy(cost))}
                            for time in ['2026-11-08T10:00:00Z', '2026-11-08T11:00:00Z']]}
    return record, collection, raw, report, seal, export, payloads, rollout


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.data = fixture(Path(self.temp.name))

    def test_native_measurements_and_exact_provenance(self):
        record, collection, raw, report, *_ = self.data
        self.assertEqual(report['observed_model'], MODEL)
        self.assertEqual(report['values']['tokens_in'], 100)
        self.assertEqual(report['values']['turns'], 1)
        self.assertEqual(report['values']['wall_clock_s'], 2)
        self.assertEqual(report['values']['tool_operations'], 1)
        self.assertIsNone(report['values']['permissions.asked'])
        self.assertIn('permissions.asked', report['unavailable'])
        observed = capture.observations(collection, record, offline=False)
        self.assertEqual(observed['identity']['kind'], 'native_response')
        self.assertNotIn('permissions.asked', observed['metrics'])

    def test_configured_model_is_not_identity_and_ws_native_metadata_is(self):
        _, _, raw, *_ = self.data
        log = raw / 'agent/codex.txt'; text = log.read_text()
        log.write_text('\n'.join(line for line in text.splitlines() if 'codex_' not in line) + '\n')
        self.assertIsNone(capture.extract(raw, MODEL)['observed_model'])
        # A WS stream has the same native ServerModel event but no SSE payload.
        log.write_text('\n'.join(line for line in text.splitlines() if 'SSE event:' not in line) + '\n')
        self.assertEqual(capture.extract(raw, MODEL)['observed_model'], MODEL)

    def test_mismatch_and_missing_server_reports_are_explicit(self):
        _, _, raw, *_ = self.data
        path = raw / 'agent/codex.txt'
        path.write_text(path.read_text().replace('server reported model ' + MODEL + ' (matches requested model)',
                      'server reported model other-model while requested model was ' + MODEL))
        result = capture.extract(raw, MODEL)
        self.assertTrue(result['model_mismatch'])
        self.assertEqual(result['observed_model'], 'other-model')

    def test_duplicate_partial_and_corrupt_traces_never_make_measured_zeros(self):
        _, _, raw, _, _, _, rows, rollout = self.data
        for modified in [rows[:-1], rows[:5] + [rows[4]] + rows[5:], rows + [('unknown_future_record', {})]]:
            rollout(modified)
            result = capture.extract(raw, MODEL)
            self.assertIsNone(result['values']['tokens_in'])
            self.assertIsNone(result['values']['subagents'])
            self.assertIsNone(result['observed_model'])
        rollout(rows)
        path = raw / 'agent/codex.txt'; path.write_text(path.read_text() + '{broken\n')
        self.assertIsNone(capture.extract(raw, MODEL)['values']['turns'])

    def test_tampering_and_synthetic_evidence_cannot_be_promoted(self):
        record, collection, raw, *_ = self.data
        path = raw / 'agent/codex.txt'; path.write_text(path.read_text() + 'tampered\n')
        with self.assertRaisesRegex(ValueError, 'binding changed'):
            capture.observations(collection, record, offline=False)
        with tempfile.TemporaryDirectory() as directory:
            record, collection, _, report, *_ = fixture(Path(directory), offline=True)
            self.assertTrue(report['synthetic'])
            self.assertEqual(capture.observations(collection, record, offline=True)['metrics'], {})
            with self.assertRaises(ValueError): capture.observations(collection, record, offline=False)


class BillingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.record, self.collection, _, _, self.seal, self.export, *_ = fixture(Path(self.temp.name))

    def reconcile(self, export):
        return billing.reconcile(self.record, self.collection, self.seal, export)

    def test_stable_scoped_provider_cost_is_bound_not_estimated(self):
        receipt = self.reconcile(self.export)
        self.assertEqual(receipt['cost_usd'], 0.001)
        self.assertFalse(receipt['over_target'])
        billing.verify_receipt(self.record, self.collection, self.seal, receipt, self.export)
        receipt['cost_usd'] = 0
        with self.assertRaisesRegex(ValueError, 'receipt'): billing.verify_receipt(self.record, self.collection, self.seal, receipt, self.export)

    def test_wrong_scope_finality_source_hash_and_synthetic_exports_are_rejected(self):
        variants = []
        for key, value in [('synthetic', True), ('run_id', 'other'), ('collection_seal_sha256', 'b' * 64), ('response_set_sha256', 'b' * 64)]:
            e = deepcopy(self.export); e[key] = value; variants.append(e)
        for key, value in [('exclusive_for_entire_bucket', False), ('other_activity', True), ('project_id', 'other'), ('api_key_id', '')]:
            e = deepcopy(self.export); e['scope'][key] = value; variants.append(e)
        for key, value in [('status', 'settling'), ('all_retries_included', False), ('reviewed_at', NOW)]:
            e = deepcopy(self.export); e['review'][key] = value; variants.append(e)
        for e in variants:
            with self.subTest(export=e), self.assertRaises(ValueError): self.reconcile(e)

    def test_empty_unstable_mixed_or_unpaginated_billing_is_unknown(self):
        variants = []
        for kind in ['usage_pages', 'cost_pages']:
            for mutate in ['empty', 'more', 'other_key']:
                e = deepcopy(self.export); page = e['snapshots'][0][kind][0]
                if mutate == 'empty': page['data'][0]['results'] = []
                if mutate == 'more': page.update(has_more=True, next_page='next')
                if mutate == 'other_key': page['data'][0]['results'][0]['api_key_id'] = 'other'
                variants.append(e)
        for value in [False, float('nan'), -1]:
            e = deepcopy(self.export); e['snapshots'][0]['cost_pages'][0]['data'][0]['results'][0]['amount']['value'] = value; variants.append(e)
        e = deepcopy(self.export); e['snapshots'][1]['cost_pages'][0]['data'][0]['results'][0]['amount']['value'] = 0.002; variants.append(e)
        e = deepcopy(self.export); e['snapshots'][0]['usage_pages'][0]['data'][0]['results'][0]['num_model_requests'] = 2; variants.append(e)
        for e in variants:
            with self.assertRaises(ValueError): self.reconcile(e)

    def test_explicit_provider_zero_is_allowed_but_overrun_is_retained(self):
        for value, over in [(0, False), (2.01, True)]:
            e = deepcopy(self.export)
            for snapshot in e['snapshots']: snapshot['cost_pages'][0]['data'][0]['results'][0]['amount']['value'] = value
            receipt = self.reconcile(e)
            self.assertEqual(receipt['cost_usd'], value); self.assertIs(receipt['over_target'], over)

class PermissionCoverageTests(unittest.TestCase):
    def test_nested_native_tool_decisions_are_measured_not_assumed(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, raw, *_ = fixture(Path(directory))
            def event(name, **fields):
                attrs = {'event.name': name, 'conversation.id': 'thread-1', 'app.version': '0.167.0', **fields}
                return {'attributes': [{'key': key, 'value': {'stringValue': value}} for key, value in attrs.items()]}
            decision = event('codex.tool_decision', call_id='exec-inner', tool_name='exec_command', source='Config')
            result = event('codex.tool_result', call_id='exec-inner', tool_name='exec_command')
            outer = event('codex.tool_result', call_id='tool-1', tool_name='exec')
            path = raw / 'agent/hn-o01-otel.jsonl'
            def save(events):
                path.write_text(json.dumps({'body': {'resourceLogs': [{'scopeLogs': [{'logRecords': events}]}]}}) + '\n')
            save([decision, result, outer])
            self.assertEqual(capture.extract(raw, MODEL)['values']['permissions.asked'], 0)
            for attribute in decision['attributes']:
                if attribute['key'] == 'source': attribute['value']['stringValue'] = 'User'
            save([decision, result, outer])
            self.assertEqual(capture.extract(raw, MODEL)['values']['permissions.asked'], 1)
            for broken in [[result, outer], [decision, result], [decision, decision, result, outer]]:
                save(broken)
                self.assertIsNone(capture.extract(raw, MODEL)['values']['permissions.asked'])

    def test_numeric_errors_sse_usage_disagreement_and_changed_report_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            record, collection, raw, report, _, _, rows, rollout = fixture(Path(directory))
            rows[4][1]['usage']['input_tokens'] = True
            rollout(rows)
            self.assertIsNone(capture.extract(raw, MODEL)['values']['tokens_in'])
            with self.assertRaises(ValueError): capture.observations(collection, record, offline=False)


if __name__ == '__main__':
    unittest.main()
