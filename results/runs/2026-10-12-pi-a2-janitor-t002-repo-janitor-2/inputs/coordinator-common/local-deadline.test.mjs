import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync,writeFileSync,chmodSync,rmSync,readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execute } from '../../scripts/run.mjs';
import { assertResourceFresh } from './local-runtime.mjs';
test('B06 wall deadline detects resumed clock jump without waiting a full monotonic timeout',async t=>{
  const dir=mkdtempSync(join(tmpdir(),'wall-deadline-'));t.after(()=>rmSync(dir,{recursive:true,force:true}));const file=join(dir,'docker'),audit=join(dir,'kill.txt');
  writeFileSync(file,`#!${process.execPath}\nconst fs=require('node:fs');if(process.argv[2]==='kill'){fs.appendFileSync(${JSON.stringify(audit)},'own-container\\n');}else{setInterval(()=>{},1000);}\n`);chmodSync(file,0o755);
  let wall=1000;const timer=setTimeout(()=>wall+=90000,50);t.after(()=>clearTimeout(timer));const begin=performance.now();
  const result=await execute(['run','--name','own-container','synthetic'],{name:'own-container',timeout:60,wallNow:()=>wall,env:{...process.env,PATH:dir+':'+process.env.PATH}});
  assert.equal(result.timedOut,true);assert.ok(performance.now()-begin<3000);assert.equal(readFileSync(audit,'utf8'),'own-container\n');
});
test('B06 stale telemetry and backwards wall clock reject further local work',()=>{
  assert.doesNotThrow(()=>assertResourceFresh(10000,25000));assert.throws(()=>assertResourceFresh(10000,25001),/stale/);assert.throws(()=>assertResourceFresh(10000,9999),/clock/);
});
