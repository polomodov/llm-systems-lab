"""Replay derived LAB31 exports in a temporary fixture; no model or API calls."""
import csv
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPORT = pathlib.Path(__file__).resolve().parent / 'measurements/LAB31-apple-qwen35-9b-mlx-20261007'
RAW = REPORT / 'raw'


class ContextMetadata(unittest.TestCase):
    def test_finalization_keeps_prompt_length_separate_from_unknown_capacity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            raw = root / 'raw'
            raw.mkdir()
            shutil.copyfile(REPORT / 'manifest.json', root / 'manifest.json')
            inputs = ['finalize_results.py', 'source-pins.json', 'server-execution.json']
            for case in ['warmup', 'r1', 'r2', 'r3']:
                inputs.extend([case+'-execution.json', case+'-memory-before.json'])
            for name in inputs:
                shutil.copyfile(RAW / name, raw / name)
            primary = {name: (raw / name).read_bytes() for name in inputs if name.endswith('-execution.json')}
            result = subprocess.run([sys.executable, str(raw / 'finalize_results.py')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with (root / 'measurements.tsv').open() as stream:
                rows = list(csv.DictReader(stream, delimiter='\t'))
            self.assertEqual(len(rows), 37)
            self.assertTrue(all(row['context_tokens'] == '' for row in rows))
            self.assertTrue(any(row['observation_id'].startswith('server-') for row in rows))
            for case in ['warmup', 'r1', 'r2', 'r3']:
                prompt = next(row for row in rows if row['observation_id'] == case+'-prompt_tokens')
                self.assertEqual(prompt['value'], '42')
                self.assertEqual(prompt['status'], 'measured')
            summary = json.loads((raw / 'results-summary.json').read_text())
            self.assertIsNone(summary['context_tokens'])
            self.assertTrue(summary['context_unavailable_reason'])
            self.assertEqual(summary['prompt_tokens'], 42)
            self.assertEqual(summary['output_tokens'], 105)
            self.assertTrue(json.loads((root / 'manifest.json').read_text())['unavailable']['context_tokens'])
            self.assertEqual(primary, {name: (raw / name).read_bytes() for name in primary})

    def test_corrected_tsv_changes_only_the_context_condition(self):
        with (RAW / 'context-before-review-measurements.tsv').open() as stream:
            before = list(csv.DictReader(stream, delimiter='\t'))
        with (REPORT / 'measurements.tsv').open() as stream:
            after = list(csv.DictReader(stream, delimiter='\t'))
        self.assertEqual(len(before), len(after))
        for old, new in zip(before, after):
            self.assertEqual(old.pop('context_tokens'), '42')
            self.assertEqual(new.pop('context_tokens'), '')
            self.assertEqual(old, new)
        runtime = json.loads((RAW / 'runtime-manifest.json').read_text())
        self.assertIsNone(runtime['context_tokens'])
        self.assertTrue(runtime['context_unavailable_reason'])

    def test_original_experimental_evidence_is_unchanged(self):
        allowed = {'finalize_results.py', 'preflight.py', 'results-summary.json', 'runtime-manifest.json'}
        before = json.loads((RAW / 'context-before-review-evidence-hashes.json').read_text())
        for name, digest in before.items():
            if name not in allowed:
                self.assertEqual(hashlib.sha256((RAW / name).read_bytes()).hexdigest(), digest, name)
        current = json.loads((RAW / 'evidence-hashes.json').read_text())
        for name, digest in current.items():
            self.assertEqual(hashlib.sha256((RAW / name).read_bytes()).hexdigest(), digest, name)


if __name__ == '__main__':
    unittest.main()
