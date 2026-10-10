import importlib.util
import pathlib
import unittest

spec=importlib.util.spec_from_file_location('artifact_selection',pathlib.Path(__file__).parent/'apple/artifacts.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class ArtifactSelection(unittest.TestCase):
    def setUp(self):
        self.gguf=dict(format='GGUF',repository='publisher/model-gguf',revision='a'*40,files=[dict(local_path='/gguf',bytes=12,sha256='1'*64)])
        self.mlx=dict(format='MLX/safetensors',repository='publisher/model-mlx',revision='b'*40,files=[dict(local_path='/mlx',bytes=8,sha256='2'*64)])
    def test_reordering_does_not_select_other_format(self):
        for rows in [[self.gguf,self.mlx],[self.mlx,self.gguf]]:
            self.assertIs(module.select_artifact(dict(artifacts=rows),format='MLX/safetensors',repository='publisher/model-mlx',revision='b'*40),self.mlx)
    def test_revision_and_uniqueness_are_required(self):
        for rows,revision in [([self.gguf,self.mlx],'c'*40),([self.mlx,self.mlx],'b'*40)]:
            with self.assertRaises(ValueError):module.select_artifact(dict(artifacts=rows),format='MLX/safetensors',repository='publisher/model-mlx',revision=revision)
    def test_other_format_or_wrong_size_cannot_cover_model_identity(self):
        for files in [[dict(path='/gguf',bytes=12,sha256='1'*64)],[dict(path='/mlx',bytes=12,sha256='2'*64)]]:
            self.assertEqual(module.missing_artifact_pins(self.mlx,dict(files=files)),['/mlx'])
        self.assertEqual(module.missing_artifact_pins(self.mlx,dict(files=[dict(path='/mlx',bytes=8,sha256='2'*64)])),[])

if __name__=='__main__':unittest.main()
