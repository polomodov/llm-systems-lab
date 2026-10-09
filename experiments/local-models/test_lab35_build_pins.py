"""Changed, omitted or added bundled dylibs must block startup before model execution."""
import hashlib,json,pathlib,tempfile,unittest
from unittest.mock import Mock,patch
from test_lab35_qualification import module

class BuildPins(unittest.TestCase):
    def fixture(self,root):
        build=root/'build';folder=build/'bin';folder.mkdir(parents=True)
        pins={}
        for name in ['llama-server','libggml','libggml-base','libggml-cpu','libggml-metal','libggml-blas','libllama','libmtmd']:
            p=folder/(name if name=='llama-server' else name+'.dylib');p.write_bytes(('synthetic '+name).encode());pins[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        return build,{'binaries':pins}

    def test_complete_reference_covers_bundled_libraries(self):
        with tempfile.TemporaryDirectory() as temporary:
            build,reference=self.fixture(pathlib.Path(temporary))
            self.assertEqual(module.verify_build_reference(build,reference),reference['binaries'])

    def test_missing_library_entry_rejects_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            build,reference=self.fixture(pathlib.Path(temporary));reference['binaries'].pop(str(build/'bin/libllama.dylib'))
            with self.assertRaisesRegex(AssertionError,'Unpinned bundled'):module.verify_build_reference(build,reference)

    def test_added_unpinned_versioned_alias_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            build,reference=self.fixture(pathlib.Path(temporary));(build/'bin/libllama.0.dylib').symlink_to('libllama.dylib')
            with self.assertRaisesRegex(AssertionError,'Unpinned bundled'):module.verify_build_reference(build,reference)

    def test_changed_dylib_stops_before_popen(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);build,reference=self.fixture(root);raw=root/'raw';raw.mkdir()
            (raw/'build-reference.json').write_text(json.dumps(reference));model=root/'model.gguf';model.write_bytes(b'synthetic model')
            row={'commands':{'sample':{'returncode':0}},'pressure_level':1,'free_pages_bytes':8*2**30,'speculative_pages_bytes':0,'pressure_free_percentage':75,'swap_used_bytes':0,'on_ac_power':True,'ac_power_mode':0}
            (build/'bin/libggml-metal.dylib').write_bytes(b'changed synthetic dylib')
            server_sha=reference['binaries'][str(build/'bin/llama-server')]
            with patch.object(module,'BUILD',build),patch.object(module,'RAW',raw),patch.object(module,'MODEL',model),patch.object(module,'MODEL_SHA',hashlib.sha256(model.read_bytes()).hexdigest()),patch.object(module,'SERVER_SHA',server_sha),patch.object(module,'sample',return_value=row),patch.object(module,'foreign_models',return_value={}),patch.object(module.socket,'socket'),patch.object(module.subprocess,'Popen') as start:
                with self.assertRaisesRegex(AssertionError,'Build hash mismatch'):module.Campaign().startup()
            start.assert_not_called()

if __name__=='__main__':unittest.main()
