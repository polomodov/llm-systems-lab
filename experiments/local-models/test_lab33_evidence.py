import importlib.util
import pathlib
import hashlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('lms_evidence', ROOT / 'experiments/local-models/apple/lms_evidence.py')
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)

class EvidenceTests(unittest.TestCase):
    def test_mapped_library_and_wait_only_are_not_compute(self):
        text = '''Call graph:
    + 85 ggml_metal_synchronize  (in libggml-metal.dylib) + 40 [0x123]
Total number in stack (recursive counted multiple, when >=5):
    85 ggml_metal_graph_compute (in libggml-metal.dylib)
Binary Images:
0x123 - 0x456 libggml-metal.dylib /tmp/libggml-metal.dylib
'''
        self.assertEqual(evidence.active_metal_frames(text), [])
        self.assertEqual(evidence.active_metal_frames('Binary Images:\n' + text.split('Binary Images:')[1]), [])

    def test_counted_compute_frame_is_accepted_only_in_call_graph(self):
        frame = '    + ! | 7 ggml_metal_op_mul_mat  (in libggml-metal.dylib) + 40 [0x123]'
        self.assertEqual(evidence.active_metal_frames('Call graph:\n' + frame + '\nBinary Images:\n' + frame), [frame])
        self.assertEqual(evidence.active_metal_frames(frame), [])
        self.assertEqual(evidence.active_metal_frames('Call graph:\n' + frame.replace('op_mul_mat', 'op_unknown')), [])

    def test_all_four_recorded_samples_have_active_compute(self):
        folder = ROOT / 'experiments/local-models/measurements/LAB33-apple-sdk-stable-window-20261010/raw/lms-gguf'
        samples = list(folder.glob('backend-*/sample-*.txt'))
        self.assertEqual(len(samples), 4)
        for sample in samples:
            with self.subTest(sample=sample.name):
                frames = evidence.active_metal_frames(sample.read_text())
                self.assertTrue(frames)
                self.assertTrue(all('0x' in frame for frame in frames))

    def test_unload_resets_only_on_success(self):
        state = {'loaded': True}
        calls = []
        evidence.unload_owned(lambda *args: calls.append(args), 'owned-alias', 'folder', state)
        self.assertFalse(state['loaded'])
        self.assertEqual(calls, [(['unload', 'owned-alias'], 'unload', 'folder', 30)])
        state['loaded'] = True
        def failure(*args):
            raise RuntimeError('unload failed')
        with self.assertRaisesRegex(RuntimeError, 'unload failed'):
            evidence.unload_owned(failure, 'owned-alias', 'folder', state)
        self.assertTrue(state['loaded'])

    def test_new_helper_requires_a_complete_matching_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            helper=pathlib.Path(temp)/'lms_evidence.py'
            helper.write_text('registered source')
            pin=dict(path=str(helper),bytes=helper.stat().st_size,sha256=hashlib.sha256(helper.read_bytes()).hexdigest())
            evidence.require_helper_pin(dict(files=[pin]),helper)
            for files in ([],[dict(pin,sha256='0'*64)],[dict(pin,bytes=0)]):
                with self.assertRaisesRegex(ValueError,'Fresh prestart pins'):
                    evidence.require_helper_pin(dict(files=files),helper)
