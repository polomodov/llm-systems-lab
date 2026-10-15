// The broker has no upstream socket. Only the trusted host worker can lease jobs.
import http from 'node:http';
import { randomUUID, timingSafeEqual } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { validateDeployment, validateLocalRequest } from './local-inference.mjs';
export async function boundedBody(req,limit) {
  const chunks=[];let size=0;
  for await(const chunk of req) { size+=chunk.length;if(size>limit)throw new Error('Body limit exceeded');chunks.push(chunk); }
  return Buffer.concat(chunks);
}
const send=(res,status,value)=>{res.writeHead(status,{'content-type':'application/json'});res.end(JSON.stringify(value));};
export function createLocalBroker(deployment,token,{timeoutMs=300000,maxBody=1024*1024,maxResponse=4*1024*1024,audit=()=>{}}={}) {
  validateDeployment(deployment);if(typeof token!=='string' || token.length<32)throw new Error('Private broker capability required');
  const jobs=new Map();let closed=false;
  const finish=(job,status,payload)=>{clearTimeout(job.timer);jobs.delete(job.id);if(!job.res.destroyed)send(job.res,status,payload);};
  const agent=http.createServer(async(req,res)=>{
    try {
      if(req.headers.host!=='egress:8080' || req.url.startsWith('http') || req.headers['x-target-url'] || req.headers['x-upstream'] || req.headers['x-forwarded-host'])return send(res,403,{error:'Destination selection denied'});
      if(req.method==='GET' && req.url==='/health')return send(res,200,{status:'ok'});
      if(req.method!=='POST' || req.url!=='/v1/chat/completions')return send(res,403,{error:'Route denied'});
      if(closed || jobs.size > 0)return send(res,429,{error:'One inference request at a time'});
      const body=validateLocalRequest(JSON.parse(await boundedBody(req,maxBody)),deployment);
      const job={id:randomUUID(),body,res,canceled:false,leased:false,timer:null};jobs.set(job.id,job);
      res.once('close',()=>{if(!res.writableEnded)job.canceled=true;});
      job.timer=setTimeout(()=>{job.canceled=true;finish(job,504,{error:'Local inference deadline'});},timeoutMs);
      audit({type:'local_request',id:job.id,model:body.model});
    } catch(error) {if(!res.headersSent)send(res,400,{error:error.message.startsWith('Local deployment:')?error.message:'Invalid or oversized local request'});else res.destroy();}
  });
  agent.on('connect',(_req,socket)=>socket.end('HTTP/1.1 403 Forbidden\r\n\r\n'));
  const control=http.createServer(async(req,res)=>{
    try {
      const supplied=Buffer.from(req.headers.authorization??''),expected=Buffer.from('Bearer '+token);
      if(supplied.length!==expected.length || !timingSafeEqual(supplied,expected))return send(res,403,{error:'Control capability denied'});
      if(req.method==='GET' && req.url==='/lease') {
        const job=[...jobs.values()].find(j=>!j.canceled && !j.leased);if(!job)return send(res,200,{job:null});job.leased=true;return send(res,200,{job:{id:job.id,body:job.body}});
      }
      const match=/^\/state\/([a-f0-9-]{36})$/.exec(req.url);
      if(req.method==='GET' && match)return send(res,200,{canceled:!jobs.has(match[1]) || jobs.get(match[1]).canceled});
      if(req.method==='POST' && req.url==='/result') {
        const payload=JSON.parse(await boundedBody(req,Math.ceil(maxResponse*4/3)+2048)),job=jobs.get(payload.id);
        if(!job)return send(res,410,{error:'Job gone'});
        const bytes=Buffer.from(payload.body??'','base64');
        if(bytes.length>maxResponse || !Number.isInteger(payload.status) || ![200,502,504].includes(payload.status)) {finish(job,502,{error:'Worker response limit/status'});return send(res,400,{error:'Worker response limit/status'});}
        clearTimeout(job.timer);jobs.delete(job.id);
        if(!job.canceled && !job.res.destroyed) {
          job.res.writeHead(payload.status,{'content-type':payload.status===200?'text/event-stream':'application/json'});job.res.end(bytes);
        }
        return send(res,200,{accepted:true});
      }
      send(res,403,{error:'Control route denied'});
    }catch{if(!res.headersSent)send(res,400,{error:'Invalid worker response'});else res.destroy();}
  });
  for(const server of [agent,control]) {server.requestTimeout=timeoutMs+1000;server.headersTimeout=10000;server.maxHeadersCount=32;}
  return {agent,control,close:async()=>{closed=true;for(const job of jobs.values()){job.canceled=true;finish(job,503,{error:'Broker stopping'});}for(const s of [agent,control]){s.closeAllConnections();if(s.listening)await new Promise(resolve=>s.close(resolve));}}};
}
if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href) {
  const d=JSON.parse(readFileSync('/control/local-deployment.json','utf8'));
  const broker=createLocalBroker(d,process.env.LAB_BRIDGE_TOKEN);delete process.env.LAB_BRIDGE_TOKEN;
  broker.agent.listen(8080,'0.0.0.0');broker.control.listen(8081,'0.0.0.0');
  for(const signal of ['SIGINT','SIGTERM'])process.on(signal,async()=>{await broker.close();process.exit(0);});
}
