"""Qualification can be complete while LAB35 remains blocked; protect raw evidence."""
import json,pathlib,shutil,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parent/'measurements/LAB35-apple-http-preregistered-20261009'
class QualificationExport(unittest.TestCase):
    def run_export(self,root):return subprocess.run([sys.executable,'-B',str(root/'raw/export_qualification.py')],capture_output=True,text=True)
    def test_apple_success_does_not_unblock_pair_or_agent_campaign(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)/'report';shutil.copytree(ROOT,root);snapshots=[]
            for _ in range(2):
                result=self.run_export(root);self.assertEqual(result.returncode,0,result.stderr)
                s=json.loads((root/'raw/summary.json').read_text())
                self.assertEqual(s['status'],'blocked');self.assertEqual(s['http_requests'],16);self.assertEqual(s['http_errors'],0)
                self.assertEqual(s['attempts'],{'completed':21,'not-run':16})
                self.assertTrue(all(v['http_qualification_completed'] for v in s['variants'].values()))
                self.assertTrue(s['variants']['metal-standard']['libraries_verified_at_execution'])
                self.assertTrue(s['variants']['metal-standard']['qualification_completed'])
                self.assertFalse(s['variants']['metal-tensor']['libraries_verified_at_execution'])
                self.assertFalse(s['variants']['metal-tensor']['qualification_completed'])
                self.assertEqual(len(s['variants']['metal-tensor']['missing_library_pins_at_execution']),21)
                self.assertIsNone(s['ryzen_comparison']);self.assertIsNone(s['agent_comparison'])
                self.assertEqual(json.loads((root/'manifest.json').read_text())['run_ids'],[])
                snapshots.append({p:(root/p).read_bytes() for p in ['manifest.json','measurements.tsv','raw/summary.json','raw/evidence-sha256.json']})
            self.assertEqual(*snapshots)
    def reject(self,change):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)/'report';shutil.copytree(ROOT,root);change(root)
            paths=['manifest.json','measurements.tsv','raw/summary.json','raw/evidence-sha256.json'];before={p:(root/p).read_bytes() for p in paths}
            result=self.run_export(root);self.assertNotEqual(result.returncode,0)
            self.assertEqual(before,{p:(root/p).read_bytes() for p in paths})
    def test_changed_primary_final_content_rejects_admission(self):
        def change(root):
            directory=root/'raw/metal-standard/chat-r1';p=directory/'request-0001.response.bin';data=json.loads(p.read_bytes());data['choices'][0]['message']['content']='LAB_WRONG';body=json.dumps(data).encode();p.write_bytes(body)
            p=directory/'request-0001.json';r=json.loads(p.read_text());r['response_bytes']=len(body);p.write_text(json.dumps(r))
            p=directory/'summary.json';s=json.loads(p.read_text());s['results'][0]=r;p.write_text(json.dumps(s))
        self.reject(change)
    def test_recorded_usage_cannot_replace_primary_usage(self):
        def change(root):
            directory=root/'raw/metal-tensor/load-r1';p=directory/'request-0001.json';r=json.loads(p.read_text());r['completion_tokens']-=1;p.write_text(json.dumps(r))
            p=directory/'summary.json';s=json.loads(p.read_text());s['results'][0]=r;p.write_text(json.dumps(s))
        self.reject(change)
if __name__=='__main__':unittest.main()
