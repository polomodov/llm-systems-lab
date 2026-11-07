"""No Docker or provider requests: authorization, evidence and settlement gates."""
from datetime import datetime, timedelta, timezone
import json
import asyncio
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import single_trial as runner
from common import BASE, NATIVE, read, sha, write


class TrialGateTests(unittest.TestCase):
    def setUp(self):
        slot = read(NATIVE / 'plan.json')['slots'][0]
        self.bundle = runner.ROOT / 'results/runs' / slot['run_id']
        self.record = read(self.bundle / 'run.json')
        self.permit = {'kind': 'harbor-single-trial-authorization-v1', 'allow_paid': True,
            'max_trials': 1, 'run_id': self.record['run_id'], 'slot_id': slot['slot_id'],
            'plan_sha256': sha(self.bundle / 'inputs/plan.json'),
            'inputs_sha256': self.record['inputs']['manifest_sha256'],
            'runner_sha256': sha(Path(runner.__file__)), 'common_sha256': sha(BASE / 'common.py'),
            'accounting_sha256': sha(NATIVE / 'accounting.py'),
            'budget_target_usd': 2, 'approved_by': 'fixture-operator', 'billing_project': 'fixture-project',
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), 'previous_run_ids': []}

    def test_exact_authorization_and_expiry_are_required(self):
        runner.validate_permit(self.permit, self.record, self.bundle)
        for patch in [{'allow_paid': False}, {'max_trials': 2}, {'run_id': 'other'},
                      {'kind': 'offline-fixture'}, {'runner_sha256': '0' * 64},
                      {'plan_sha256': '0' * 64}, {'common_sha256': '0' * 64},
                      {'expires_at': '2000-01-01T00:00:00Z'}, {'previous_run_ids': None}]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                runner.validate_permit(self.permit | patch, self.record, self.bundle)

    def test_library_execution_cannot_bypass_authorization(self):
        with self.assertRaisesRegex(ValueError, 'authorization'):
            asyncio.run(runner.run_trial(runner.ROOT, self.bundle, 'unix:///unused', False, None))

    def test_selected_key_parser_uses_only_one_literal_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('OTHER_KEY=not-forwarded\nOPENAI_API_KEY=fixture-key\n')
            self.assertEqual(runner.selected_credential(path, 'OPENAI_API_KEY'), 'fixture-key')
            for text in ['OPENAI_API_KEY=one\nOPENAI_API_KEY=two\n', 'OPENAI_API_KEY=$(false)\n', 'OTHER_KEY=other\n']:
                path.write_text(text)
                with self.assertRaises(ValueError):
                    runner.selected_credential(path, 'OPENAI_API_KEY')

    def test_live_finalization_blocks_unknown_billing_before_import(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            write(bundle / 'run.json', {'run_id': 'fixture'})
            collection = bundle / 'collection'; collection.mkdir()
            write(collection / 'state.json', {'run_id': 'fixture', 'offline': False})
            (bundle / 'trace').mkdir()
            write(bundle / 'trace/collection-seal.json', {'run_id': 'fixture', 'offline': False,
                  'files': runner.a.inventory(collection)})
            with self.assertRaisesRegex(ValueError, 'settled billing'):
                runner.import_collection(bundle, bundle, collection, offline=False)
            self.assertFalse((bundle / 'trace/import-source').exists())
            (collection / 'state.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'changed after sealing'):
                runner.import_collection(bundle, bundle, collection, offline=False)

    def test_live_configuration_keeps_direct_provider_and_separate_task_policy(self):
        slot = read(NATIVE / 'plan.json')['slots'][0]
        config = runner.config_for(slot, Path('/sealed/package'), Path('/owned/output'), 'fixture', False)
        self.assertNotIn('base_url', config['agent'])
        self.assertNotIn('env', config['environment'])
        self.assertEqual(config['agent']['kwargs']['skip_install'], True)
        self.assertNotIn('retry', config)

    def test_missing_authorization_never_reaches_docker_or_credentials(self):
        with patch.object(sys, 'argv', ['single_trial.py', 'execute', '--run-id', self.record['run_id']]), \
             patch.object(runner, 'isolate') as isolate, patch.object(runner, 'run_trial') as execute, \
             patch.object(runner, 'selected_credential') as credential:
            with self.assertRaisesRegex(ValueError, 'Paid execution is disabled'):
                asyncio.run(runner.main())
            isolate.assert_not_called()
            execute.assert_not_called()
            credential.assert_not_called()

    def test_global_execution_lock_refuses_concurrent_controller(self):
        with runner.execution_lock():
            with self.assertRaises(FileExistsError):
                with runner.execution_lock():
                    self.fail('Concurrent execution should be rejected')


if __name__ == '__main__':
    unittest.main()
