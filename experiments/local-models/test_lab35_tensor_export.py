"""Fresh tensor evidence must prove library identity before native launch."""
import hashlib,json,pathlib,shutil,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parent/'measurements/LAB35-apple-tensor-pinned-20261009'

class TensorExport(unittest.TestCase):
    def run_export(self,root):
        return subprocess.run([sys.executable,'-B',str(root/'raw/export_tensor.py')],capture_output=True,text=True)

    def reseal(self,root):
        p=root/'raw/primary-evidence-sha256.json';pins=json.loads(p.read_text())
        for name in pins:pins[name]=hashlib.sha256((root/'raw'/name).read_bytes()).hexdigest()
        p.write_text(json.dumps(pins,indent=2)+'\n')

    def test_fresh_repeat_complete_and_replay_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)/'report';shutil.copytree(ROOT,root);snapshots=[]
            for _ in range(2):
                result=self.run_export(root);self.assertEqual(result.returncode,0,result.stderr)
                s=json.loads((root/'raw/summary.json').read_text());v=s['variants']['metal-tensor']
                self.assertEqual(s['status'],'completed');self.assertEqual(s['http_requests'],8);self.assertEqual(s['http_errors'],0)
                self.assertEqual(s['attempts'],{'completed':11})
                for key in ['qualification_completed','libraries_verified_at_execution','pins_checked_before_popen','pin_audit_matches']:self.assertTrue(v[key],key)
                self.assertEqual(v['missing_library_pins_at_execution'],[])
                self.assertIsNone(s['ryzen_comparison']);self.assertIsNone(s['agent_comparison'])
                m=json.loads((root/'manifest.json').read_text());self.assertEqual(m['run_ids'],[]);self.assertIn('full_lab35',m['unavailable'])
                snapshots.append({name:(root/name).read_bytes() for name in ['manifest.json','measurements.tsv','raw/summary.json','raw/evidence-sha256.json']})
            self.assertEqual(*snapshots)

    def blocked(self,change):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)/'report';shutil.copytree(ROOT,root);change(root);self.reseal(root)
            result=self.run_export(root);self.assertEqual(result.returncode,0,result.stderr)
            s=json.loads((root/'raw/summary.json').read_text());self.assertEqual(s['status'],'blocked')
            self.assertFalse(s['variants']['metal-tensor']['qualification_completed'])

    def test_missing_execution_library_pin_cannot_be_inferred_from_reference(self):
        def change(root):
            p=root/'raw/metal-tensor/startup-process.json';s=json.loads(p.read_text());key=next(k for k in s['pinned_binaries'] if k.endswith('libggml-metal.dylib'));del s['pinned_binaries'][key];p.write_text(json.dumps(s))
        self.blocked(change)

    def test_post_launch_verification_cannot_admit_repeat(self):
        def change(root):
            p=root/'raw/metal-tensor/startup-process.json';s=json.loads(p.read_text());s['binaries_verified_at']=json.loads((root/'raw/metal-tensor/shutdown-execution.json').read_text())['ended_at'];p.write_text(json.dumps(s))
        self.blocked(change)

    def reject(self,change,reseal=False):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)/'report';shutil.copytree(ROOT,root);change(root)
            if reseal:self.reseal(root)
            paths=['manifest.json','measurements.tsv','raw/summary.json','raw/evidence-sha256.json'];before={p:(root/p).read_bytes() for p in paths}
            result=self.run_export(root);self.assertNotEqual(result.returncode,0)
            self.assertEqual(before,{p:(root/p).read_bytes() for p in paths})

    def test_changed_registered_request_rejected(self):
        self.reject(lambda root:(root/'raw/chat-request.json').write_text('{}'))

    def test_changed_primary_bytes_rejected(self):
        self.reject(lambda root:(root/'raw/metal-tensor/load-r1/request-0001.response.bin').write_bytes(b'{}'))

    def test_invalid_chat_content_rejected_even_with_matching_inventory(self):
        def change(root):
            d=root/'raw/metal-tensor/chat-r1';p=d/'request-0001.response.bin';s=json.loads(p.read_bytes());s['choices'][0]['message']['content']='LAB_WRONG';body=json.dumps(s).encode();p.write_bytes(body)
            p=d/'request-0001.json';record=json.loads(p.read_text());record['response_bytes']=len(body);p.write_text(json.dumps(record))
            p=d/'summary.json';s=json.loads(p.read_text());s['results'][0]=record;p.write_text(json.dumps(s))
        self.reject(change,reseal=True)

    def test_usage_must_match_primary_response(self):
        def change(root):
            d=root/'raw/metal-tensor/load-r1';p=d/'request-0001.json';record=json.loads(p.read_text());record['completion_tokens']-=1;p.write_text(json.dumps(record))
            p=d/'summary.json';s=json.loads(p.read_text());s['results'][0]=record;p.write_text(json.dumps(s))
        self.reject(change,reseal=True)

if __name__=='__main__':unittest.main()
