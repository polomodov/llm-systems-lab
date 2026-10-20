import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const {startNative,requestLocal}=await import(pathToFileURL(resolve('experiments/common/local-runtime.mjs')));
const raw=resolve('experiments/local-models/measurements/LAB08-apple-provider-bridge-20261012/raw');
const d=JSON.parse(readFileSync(raw+'/deployment.json'));
const result={started_at:new Date().toISOString(),status:'failed'};
let native;
try {
 native=await startNative(d,raw+'/native');
 await native.verify();
 const body={model:d.alias,messages:[{role:'user',content:'Reply with exactly LAB_BRIDGE_READY.'}],max_tokens:2048,temperature:0,seed:1,stream:false};
 writeFileSync(raw+'/native-request.json',JSON.stringify(body,null,2)+'\n');
 const response=await requestLocal(native.base+'/v1/chat/completions',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
 writeFileSync(raw+'/native-response.json',response.body);
 if(response.status!==200 || !JSON.parse(response.body).choices[0].message.content.includes('LAB_BRIDGE_READY'))throw new Error('Native chat qualification failed');
 await native.verify(); result.chat=true;
 // Block coordinator only: native process continues, no system clock/power changes.
 const wait=new Int32Array(new SharedArrayBuffer(4)); Atomics.wait(wait,0,0,16000);
 try {await native.verify();throw new Error('Stale guard accepted work');}catch(e){if(!/stale/.test(e.message))throw e;result.stale_rejected=e.message;}
 result.status='completed';
}catch(e){result.error=e.stack;process.exitCode=1;}
finally {if(native)await native.close();result.finished_at=new Date().toISOString();writeFileSync(raw+'/native-qualification.json',JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));}
