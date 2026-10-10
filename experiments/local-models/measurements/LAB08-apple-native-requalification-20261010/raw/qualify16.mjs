import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { startNative, requestLocal } from '../../../../../experiments/common/local-runtime.mjs';
import { validateLocalRequest, validateLocalResponse } from '../../../../../scripts/lib/local-inference.mjs';
const raw=fileURLToPath(new URL('./ctx16/',import.meta.url));
const d=JSON.parse(readFileSync(raw+'deployment.json'));
const save=(name,value)=>writeFileSync(raw+name,JSON.stringify(value,null,2)+'\n');
const started=Date.now(),abort=new AbortController();let native,expired=false;
const guard=setInterval(()=>{if(Date.now()-started>180000){expired=true;abort.abort();native?.close();}},250);
const summary={started_at:new Date(started).toISOString(),requests:[],accepted:false,error:null};
try {
  native=await startNative(d,raw+'native');
  if(expired)throw new Error('Qualification wall deadline');
  const body=validateLocalRequest({model:d.alias,messages:[{role:'user',content:'Reply with exactly LAB_READY and no other text.'}],stream:true,stream_options:{include_usage:true},max_tokens:2048,temperature:0,seed:1,top_p:1},d);
  save('request.json',body);
  for(let i=0;i<4;i++) {
    await native.verify();const start=Date.now();
    const r=await requestLocal(native.base+'/v1/chat/completions',{method:'POST',body:JSON.stringify(body),headers:{'content-type':'application/json'},signal:abort.signal,timeout:60000});
    writeFileSync(raw+`response-${i}.sse`,r.body);
    const parsed=validateLocalResponse(r.body,d);let content='',finish=null;
    for(const event of r.body.toString().split(/\r?\n\r?\n/)) {
      const data=event.split(/\r?\n/).filter(s=>s.startsWith('data:')).map(s=>s.slice(5).trimStart()).join('\n');
      if(!data || data==='[DONE]')continue;
      const frame=JSON.parse(data);for(const c of frame.choices){content+=c.delta?.content??'';if(c.finish_reason)finish=c.finish_reason;}
    }
    const row={repeat:i,warmup:i===0,status:r.status,wall_seconds:(Date.now()-start)/1000,content,finish,...parsed};summary.requests.push(row);save('qualification.json',summary);
    if(r.status!==200 || content!=='LAB_READY' || finish!=='stop' || !parsed.usage)throw new Error('Chat qualification failed');
    await native.verify();
  }
  await new Promise(resolve=>setTimeout(resolve,20000));await native.verify();
  summary.accepted=!expired;
}catch(e){summary.error=e.message;}
finally {
  clearInterval(guard);await native?.close();
  summary.ended_at=new Date().toISOString();summary.total_wall_seconds=(Date.now()-started)/1000;
  if(native){const shutdown=JSON.parse(readFileSync(raw+'native/shutdown-process.json'));summary.shutdown=shutdown;if(shutdown.exit?.code!==0 || shutdown.guard || shutdown.sigint_count!==1)summary.accepted=false;}
  save('qualification.json',summary);
}
console.log(JSON.stringify(summary));if(!summary.accepted)process.exitCode=1;
