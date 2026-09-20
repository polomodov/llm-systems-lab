import { test } from 'node:test';
import assert from 'node:assert/strict';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRun } from '../scripts/lib/records.mjs';
import { prepareRun } from '../scripts/prepare-run.mjs';
import { loadProfile, controlFiles } from '../scripts/lib/harnesses.mjs';
import { copyTree, inventory } from '../scripts/lib/files.mjs';
import { verifyRunIntegrity } from '../scripts/lib/integrity.mjs';
const root=fileURLToPath(new URL('../',import.meta.url));
const harnesses=['claude-code','opencode','codex','antigravity-cli','pi','mini-swe-agent','openhands','copilot-cli','amp'];
const episodes=[['a1-dossier','T001-dossier-from-sources'],['a2-janitor','T002-repo-janitor'],['a3-ledger-auditor','T003-harness-self-audit']];
function fixture(t) {
  const dest=mkdtempSync(join(tmpdir(),'harness-matrix-'));
  t.after(()=>rmSync(dest,{recursive:true,force:true}));
  const files=['README.md','AGENTS.md','CLAUDE.md','package.json','docs/method.md','docs/harnesses.md','docs/harness-ledger.md','agents/README.md','tasks/README.md','experiments/README.md','experiments/common/entrypoint.mjs','experiments/common/egress.mjs','results/schema.json'];
  for(const [agent,task] of episodes) files.push(`agents/${agent}/spec.md`,`tasks/${task}/task.md`,`tasks/${task}/setup.sh`);
  for(const id of harnesses) { const profile=loadProfile(root,id); files.push(`experiments/${id}/README.md`,`experiments/${id}/NOTES.md`,...controlFiles(profile).map(file=>`experiments/${id}/${file.source}`)); }
  for(const file of new Set(files)) { mkdirSync(dirname(join(dest,file)),{recursive:true});copyFileSync(join(root,file),join(dest,file)); }
  copyTree(join(root,'scripts'),join(dest,'scripts'));
  return dest;
}
test('all nine harnesses prepare all three public episodes with sealed provider-specific controls', t=>{
  const source=fixture(t);
  for(const id of harnesses) for(const [agent,task] of episodes) {
    const record=createRun({root:source,harness:id,agent,task});
    const prepared=prepareRun(source,record.run_id);
    const profile=loadProfile(source,id), dir=join(source,'results/runs',record.run_id);
    assert.equal(prepared.status,'prepared',`${id}/${task}`);
    assert.equal(prepared.model.provider,profile.default_provider);
    assert.equal(prepared.model.selection,profile.model_policy);
    assert.equal(prepared.model.lock,profile.model_policy==='managed');
    assert.equal(prepared.harness_changes.at(-1).ledger,profile.ledger);
    for(const file of controlFiles(profile)) assert.ok(existsSync(join(dir,'inputs/control',file.target)),`${id}:${file.target}`);
    const network=JSON.parse(readFileSync(join(dir,'inputs/control/network.json'),'utf8'));
    assert.deepEqual(network.connect_domains,[...new Set([...profile.providers[profile.default_provider].connect_domains,...(task.startsWith('T002')?['registry.npmjs.org']:[])])]);
    assert.equal(inventory(join(dir,'workspace')).some(row=>/(^|\/)(check|\.env)(\/|$)/.test(row.path)),false);
    verifyRunIntegrity(source,prepared);
  }
});
test('provider selection is frozen into the prepared record and missing providers fail without workspaces',t=>{
  const source=fixture(t);
  const good=createRun({root:source,harness:'mini-swe-agent',agent:'a2-janitor',task:'T002',provider:'openai'});
  const prepared=prepareRun(source,good.run_id);
  const policy=JSON.parse(readFileSync(join(source,'results/runs',good.run_id,'inputs/control/network.json'),'utf8'));
  assert.equal(prepared.model.provider,'openai');assert.ok(policy.connect_domains.includes('api.openai.com'));assert.ok(!policy.connect_domains.includes('api.anthropic.com'));
  const bad=createRun({root:source,harness:'codex',agent:'a2-janitor',task:'T002'});
  assert.throws(()=>prepareRun(source,bad.run_id,{provider:'anthropic'}),/not configured/);
  assert.equal(existsSync(join(source,'results/runs',bad.run_id,'inputs')),false);
});
