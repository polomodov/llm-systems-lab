import hashlib
import importlib.util
import pathlib
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('preregistration', pathlib.Path(__file__).parent / 'apple/preregistration.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PreregistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'test')
        (self.root / 'protocol.md').write_text('registered protocol\n')
        self.git('add', '.')
        self.git('-c', 'commit.gpgsign=false', 'commit', '-qm', 'preregister')
        self.commit = self.git('rev-parse', 'HEAD').strip()
        self.sha = hashlib.sha256((self.root / 'protocol.md').read_bytes()).hexdigest()
        self.files = {'protocol.md': self.sha}

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True)

    def verify(self, files=None, started='2099-01-01T00:00:00Z', head='HEAD'):
        return module.verify_preregistration(self.root, self.commit, self.files if files is None else files, started, head)

    def test_exact_retained_blob_passes(self):
        self.assertTrue(self.verify()['verified'])
        (self.root / 'protocol.md').write_text('a later change\n')
        self.assertTrue(self.verify()['verified'])  # Reads the preregistration blob, not mutable HEAD.

    def test_missing_or_changed_required_blob_blocks(self):
        self.assertFalse(self.verify({'pins.json': self.sha})['verified'])
        self.assertFalse(self.verify({'protocol.md': '0' * 64})['verified'])

    def test_late_registration_blocks(self):
        self.assertFalse(self.verify(started='2000-01-01T00:00:00Z')['verified'])

    def test_registration_outside_reviewed_ancestry_blocks(self):
        self.git('checkout', '--orphan', 'rewritten')
        self.git('rm', '-q', '--cached', 'protocol.md')
        self.git('-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-qm', 'squashed history')
        self.assertFalse(self.verify()['verified'])

    def test_empty_receipt_and_invalid_sha_block(self):
        self.assertFalse(self.verify({})['verified'])
        self.assertFalse(module.verify_preregistration(self.root, 'HEAD', self.files, '2099-01-01T00:00:00Z')['verified'])
