"""A native exit must not hide the failed block omitted by the live register."""
import json,pathlib,shutil,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parent/'measurements/LAB34-apple-load-power-retry-20261009'

class FailedSustainedExport(unittest.TestCase):
    def test_empty_live_register_preserves_primary_failed_block_and_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)/'report';shutil.copytree(ROOT,root)
            self.assertEqual(json.loads((root/'raw/sustained/series.json').read_text())['blocks'],[])
            result=subprocess.run([sys.executable,'-B',str(root/'raw/finalize_resume.py')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            summary=json.loads((root/'raw/summary.json').read_text())
            self.assertEqual(summary['status'],'blocked')
            self.assertEqual(summary['sustained']['requests'],12)
            self.assertEqual(summary['sustained']['successful'],8)
            self.assertEqual(summary['sustained']['failed'],4)
            self.assertEqual(summary['provenance']['new_requests'],74)
            self.assertEqual(summary['provenance']['all_started_requests'],150)
            self.assertEqual(summary['provenance']['all_failed_requests'],7)
            # Revalidation must not rewrite the original empty live register.
            self.assertEqual(json.loads((root/'raw/sustained/series.json').read_text())['blocks'],[])

if __name__=='__main__':unittest.main()
