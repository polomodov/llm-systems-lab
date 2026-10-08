"""Synthetic exporter regression: no model, server, or real evidence mutation."""
import ast
import csv
import json
import pathlib
import re
import statistics
import subprocess
import sys
import tempfile
import unittest

BASE = pathlib.Path(__file__).resolve().parent / 'measurements'
SOURCES = [BASE / session / 'raw/finalize_phase.py' for session in [
    'LAB32-apple-qwen35-9b-metal-20261007',
    'LAB32-apple-qwen35-9b-metal-auto-20261007',
]]


def load_exporter(source):
    # Load the actual pure export functions without the report-mutating entry point.
    tree = ast.parse(source.read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {'context_for_case', 'export_measurements'}]
    assert len(functions) == 2
    namespace = dict(csv=csv, json=json, re=re, statistics=statistics)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
    return namespace


class ContextExport(unittest.TestCase):
    def test_primary_followup_controls_and_effects_keep_their_conditions(self):
        for source in SOURCES:
            with self.subTest(source=source.parent.parent.name), tempfile.TemporaryDirectory() as temporary:
                root = pathlib.Path(temporary)
                raw = root / 'raw'
                raw.mkdir()
                attempts = {}
                expected = {}
                for context in [8192, 16384, 32768]:
                    case = f'ctx{context}-tool-r1'
                    configuration = f'metal-ctx{context}-tool'
                    attempts[case] = dict(configuration_id=configuration, status='completed')
                    for suffix in ['', '.followup']:
                        label = case + suffix
                        (raw / (label + '.metrics.json')).write_text(json.dumps({
                            'duration_s': 1.25, 'http_status': 200,
                            'ttft_content_s': None, 'ttft_reasoning_s': .1,
                            'usage': {'prompt_tokens': 42, 'completion_tokens': 8},
                        }))
                        expected[label] = (context, configuration)
                    for effect, data in [('cancel', {'release_after_client_s': .25, 'exit_code': 28}),
                                         ('overflow', {'status': 400, 'wall_seconds': .1})]:
                        case = f'ctx{context}-{effect}'
                        configuration = f'metal-ctx{context}-{effect}'
                        attempts[case] = dict(configuration_id=configuration, status='completed')
                        (raw / (case + '-execution.json')).write_text(json.dumps(data))
                        expected[case] = (context, configuration)
                control = 'control-fresh-thinking-auto-retry'
                attempts[control] = dict(configuration_id='metal-ctx8192-fresh-thinking-auto', status='completed')
                (raw / (control + '.metrics.json')).write_text(json.dumps({'duration_s': .5, 'http_status': 200}))
                expected[control] = (8192, attempts[control]['configuration_id'])
                load_exporter(source)['export_measurements'](raw, root, attempts)
                with (root / 'measurements.tsv').open() as stream:
                    rows = list(csv.DictReader(stream, delimiter='\t'))
                self.assertEqual(len(rows), 52)
                for label, (context, configuration) in expected.items():
                    selected = [row for row in rows if row['observation_id'].startswith(label + '-')]
                    self.assertTrue(selected, label)
                    self.assertTrue(all(row['context_tokens'] == str(context) for row in selected), label)
                    self.assertTrue(all(row['configuration_id'] == configuration for row in selected), label)
                self.assertTrue(any(row['status'] == 'unavailable' and row['value'] == '' for row in rows))

    def test_missing_unsupported_or_conflicting_context_is_rejected(self):
        for source in SOURCES:
            function = load_exporter(source)['context_for_case']
            for case, configuration in [('unlabelled', 'unlabelled'),
                                        ('ctx65536-chat-r1', 'metal-ctx65536-chat'),
                                        ('ctx16384-chat-r1', 'metal-ctx8192-chat')]:
                with self.subTest(source=source.name, case=case), self.assertRaises(ValueError):
                    function(case, {case: {'configuration_id': configuration}})

    def test_checkpoint_rejects_future_evidence_before_mutating_files(self):
        for source in SOURCES:
            for fixture in ['ctx16384-chat-r1.metrics.json', 'ctx32768-overflow-execution.json']:
                with self.subTest(source=source.parent.parent.name, fixture=fixture), tempfile.TemporaryDirectory() as temporary:
                    root = pathlib.Path(temporary)
                    raw = root / 'raw'
                    raw.mkdir()
                    script = raw / 'finalize_phase.py'
                    script.write_bytes(source.read_bytes())
                    (raw / fixture).write_text('{}')
                    (root / 'manifest.json').write_text('{}')
                    protected = [root / 'manifest.json', root / 'report.md', root / 'measurements.tsv']
                    for path in protected[1:]:
                        path.write_text('existing checkpoint')
                    before = {path: path.read_bytes() for path in protected}
                    result = subprocess.run([sys.executable, str(script), 'auto'], capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('8K checkpoint cannot finalize higher-context evidence', result.stderr)
                    self.assertEqual(before, {path: path.read_bytes() for path in protected})


if __name__ == '__main__':
    unittest.main()
