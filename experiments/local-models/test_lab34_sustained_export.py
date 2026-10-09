"""Offline admission boundaries on the completed sustained evidence."""
import json,pathlib,shutil,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parent/'measurements/LAB34-apple-sustained-resume-20261009'

class SustainedExport(unittest.TestCase):
    def run_export(self,root):
        return subprocess.run([sys.executable,'-B',str(root/'raw/finalize_sustained.py')],capture_output=True,text=True)

    def test_completed_interval_is_idempotent_and_history_is_not_recounted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)/'report';shutil.copytree(ROOT,root)
            snapshots=[]
            for _ in range(2):
                result=self.run_export(root);self.assertEqual(result.returncode,0,result.stderr)
                s=json.loads((root/'raw/summary.json').read_text())
                self.assertEqual(s['status'],'completed');self.assertEqual(s['attempts'],{'completed':5})
                self.assertGreaterEqual(s['sustained']['actual_seconds'],1800)
                self.assertEqual(s['sustained']['failed'],0)
                self.assertEqual(s['provenance']['previous_requests'],150)
                self.assertEqual(s['provenance']['all_failed_requests'],7)
                self.assertEqual(s['provenance']['new_requests'],s['sustained']['requests']+2)
                self.assertEqual(s['provenance']['all_started_requests'],150+s['sustained']['requests']+2)
                snapshots.append({name:(root/name).read_bytes() for name in ['manifest.json','measurements.tsv','raw/summary.json','raw/evidence-sha256.json']})
            self.assertEqual(*snapshots)

    def reject(self,change):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)/'report';shutil.copytree(ROOT,root);change(root)
            files=['manifest.json','measurements.tsv','raw/summary.json','raw/evidence-sha256.json']
            before={name:(root/name).read_bytes() for name in files}
            result=self.run_export(root);self.assertNotEqual(result.returncode,0)
            self.assertEqual(before,{name:(root/name).read_bytes() for name in files})

    def test_shorter_interval_cannot_be_admitted(self):
        def change(root):
            p=root/'raw/sustained/series.json';s=json.loads(p.read_text());s['actual_seconds']=1799.9;p.write_text(json.dumps(s))
        self.reject(change)

    def test_swap_in_completed_timeline_cannot_be_admitted(self):
        def change(root):
            p=root/'raw/memory-timeline.jsonl';lines=p.read_text().splitlines();r=json.loads(lines[0]);r['swap_used_bytes']=1;lines[0]=json.dumps(r);p.write_text('\n'.join(lines)+'\n')
        self.reject(change)

    def test_wrong_concurrency_selection_cannot_be_admitted(self):
        def change(root):
            p=root/'raw/sustained-selection.json';s=json.loads(p.read_text());s['concurrency']=4;p.write_text(json.dumps(s))
        self.reject(change)

if __name__=='__main__':unittest.main()
