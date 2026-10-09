import test from 'node:test';
import assert from 'node:assert/strict';
import { copyFileSync,mkdtempSync,mkdirSync,readFileSync,rmSync,writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname,join } from 'node:path';
import { createRun,writeRun,validateRun } from '../../scripts/lib/records.mjs';
import { prepareRun } from '../../scripts/prepare-run.mjs';
import { verifyRunIntegrity } from '../../scripts/lib/integrity.mjs';
import { summarize } from '../../scripts/compare.mjs';
import { copyTree } from '../../scripts/lib/files.mjs';
import { credentials } from '../../scripts/run.mjs';
import { loadProfile,validateProfile } from '../../scripts/lib/harnesses.mjs';
import { deployment } from './local-fixture.mjs';
const repository=new URL('../../',import.meta.url).pathname;
function fixture(t) {
  const root=mkdtempSync(join(tmpdir(),'local-metadata-'));t.after(()=>rmSync(root,{recursive:true,force:true}));
  for(const path of ['docs/harness-ledger.md','agents/a2-janitor/spec.md','tasks/T002-repo-janitor/task.md','tasks/T002-repo-janitor/setup.sh','results/schema.json']){mkdirSync(dirname(join(root,path)),{recursive:true});copyFileSync(join(repository,path),join(root,path));}
  for(const path of ['scripts','experiments/common','experiments/pi'])copyTree(join(repository,path),join(root,path));return root;
}
function prepared(root,d) {const initial=createRun({root,harness:'pi',agent:'a2-janitor',task:'T002',model:d.alias,provider:'local'});const path=join(root,'deployment.json');writeFileSync(path,JSON.stringify(d));return prepareRun(root,initial.run_id,{provider:'local',localDeployment:path});}
test('B09 local prepare seals complete manifest and credentials are not required or imported',t=>{
  const root=fixture(t);const r=prepared(root,deployment());assert.equal(r.model.provider,'local');assert.equal(r.local_inference.observed,null);assert.deepEqual(credentials(root,[]),{});assert.deepEqual(validateRun(r,{root}),[]);verifyRunIntegrity(root,r);
  const path=join(root,'results/runs',r.run_id,'inputs/control/local-deployment.json');const altered=JSON.parse(readFileSync(path));altered.protocol.context_tokens=16384;writeFileSync(path,JSON.stringify(altered));assert.throws(()=>verifyRunIntegrity(root,r),/snapshot changed/);
});
test('B07 same alias and task with changed context has separate compare groups',t=>{
  const root=fixture(t),a=deployment(),b=deployment();b.protocol.context_tokens=16384;
  for(const d of [a,b]){const r=prepared(root,d);r.status='aborted';r.verdict.result='aborted';r.harness.version='0.73.1';r.model.identity_evidence='synthetic aborted fixture';r.permissions.mode='synthetic';r.sandbox={kind:'container',network:'allowlist'};r.execution={...r.execution,command:['synthetic'],cwd:'/workspace/sample',started_at:'2026-10-09T00:00:00.000Z',finished_at:'2026-10-09T00:00:01.000Z',image_id:'synthetic-image',timeout_s:10,network_policy:'synthetic',budget_policy:'observed'};r.loop.stop_reason='synthetic_failure';writeRun(root,r);}
  const report=summarize(root);assert.equal(report.groups.length,2);assert.notEqual(report.groups[0].conditions.local_inference,report.groups[1].conditions.local_inference);
});
test('B04 local policy rejects cloud domains and cannot be added to another harness',()=>{
  const profile=loadProfile(repository,'pi');const bad=structuredClone(profile);bad.providers.local.connect_domains=['api.openai.com'];assert.throws(()=>validateProfile(bad),/local provider/);assert.throws(()=>validateProfile({...profile,id:'codex'}),/local provider/);
});
