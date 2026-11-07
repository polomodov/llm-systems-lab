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
            'collector_sha256': sha(BASE / 'hn_o01.py'), 'reconciler_sha256': sha(BASE / 'hn_o01_billing.py'), 'telemetry_sha256': sha(BASE / 'otel_receiver.mjs'),
            'budget_target_usd': 2, 'approved_by': 'fixture-operator', 'billing_project': 'fixture-project', 'billing_api_key_id': 'key-fixture',
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), 'previous_run_ids': []}

    def test_exact_authorization_and_expiry_are_required(self):
        runner.validate_permit(self.permit, self.record, self.bundle)
        for patch in [{'allow_paid': False}, {'max_trials': 2}, {'run_id': 'other'},
                      {'kind': 'offline-fixture'}, {'runner_sha256': '0' * 64}, {'collector_sha256': '0' * 64},
                      {'reconciler_sha256': '0' * 64}, {'telemetry_sha256': '0' * 64}, {'billing_api_key_id': None},
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
            (bundle / 'inputs').mkdir()
            write(bundle / 'inputs/pilot-slot.json', {'slot_id': 'fixture'})
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

class FilesystemBoundaryTests(unittest.TestCase):
    def test_operator_inputs_reject_paths_links_and_writable_files(self):
        import os
        import common
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'operator'; root.mkdir()
            outside = Path(directory) / 'external.json'; outside.write_text('{"external":true}')
            (root / 'valid.json').write_text('{"fixture":true}')
            (root / 'linked.json').symlink_to(outside)
            os.link(outside, root / 'hard.json')
            (root / 'writable.json').write_text('{}'); (root / 'writable.json').chmod(0o666)
            with patch.object(common, 'OPERATOR_ROOT', root):
                self.assertEqual(common.operator_document('valid.json')[1], {'fixture': True})
                for name in ['../external.json', str(outside), 'operator-other/file.json',
                             'linked.json', 'hard.json', 'writable.json']:
                    with self.subTest(name=name), self.assertRaises((ValueError, OSError)):
                        common.operator_document(name)
            self.assertEqual(outside.read_text(), '{"external":true}')

    def test_redaction_never_writes_through_file_directory_or_hard_links(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / 'outside'; outside.mkdir()
            sentinel = outside / 'sentinel'; sentinel.write_text('secret')
            for kind in ['file', 'directory', 'hard']:
                collection = root / kind; collection.mkdir()
                if kind == 'file': (collection / 'link').symlink_to(sentinel)
                elif kind == 'directory': (collection / 'link').symlink_to(outside, target_is_directory=True)
                else: os.link(sentinel, collection / 'link')
                with self.subTest(kind=kind), self.assertRaises((ValueError, OSError)):
                    runner.redact_tree(collection, 'secret')
                self.assertEqual(sentinel.read_text(), 'secret')
            collection = root / 'regular'; collection.mkdir()
            (collection / 'evidence.json').write_text('before secret after')
            runner.redact_tree(collection, 'secret')
            self.assertEqual((collection / 'evidence.json').read_text(), 'before [REDACTED] after')

    def test_offline_library_rejects_real_catalog_before_importing_harbor(self):
        with self.assertRaisesRegex(ValueError, 'scratch catalog'):
            asyncio.run(runner.run_trial(runner.ROOT, runner.ROOT / 'results/runs/unused', 'unix:///unused', True))


if __name__ == '__main__':
    unittest.main()
