// Deterministic loopback-only protocol fixture. Never connects to a provider.
import http from 'node:http';
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';

const toolCommand = `node -e 'const fs=require("fs"); const input=JSON.parse(fs.readFileSync("/app/input.json","utf8")); fs.mkdirSync("/app/output",{recursive:true}); fs.writeFileSync("/app/output/result.json",JSON.stringify([...new Set(input.map(x=>x.trim().toLowerCase()).filter(Boolean))].sort())+"\\n"); fs.writeFileSync("/app/output/model-tool.json",JSON.stringify({fixture:true,uid:process.getuid(),tool_executed:true,cap_eff:fs.readFileSync("/proc/self/status","utf8").split("\\n").find(x=>x.startsWith("CapEff:")).split(":")[1].trim()})+"\\n")'`;
function chosenTool(body) {
  const tools = [...(body.tools ?? []), ...(body.input ?? []).filter(item=>item.type==='additional_tools').flatMap(item=>item.tools??[])];
  function flatten(items, namespace) {
    return items.flatMap(t=>t.type==='namespace'?flatten(t.tools??[],t.name):[{...(t.function??t),...(namespace?{namespace}:{})}]);
  }
  return flatten(tools).find(t=>['Bash','bash','exec_command','shell_command','shell','exec'].includes(t.name));
}
function argsFor(tool, command=toolCommand) {
  const props = (tool.input_schema ?? tool.parameters ?? {}).properties ?? {};
  if ('cmd' in props) return {cmd:command};
  if ('command' in props && props.command.type === 'array') return {command:['bash','-lc',command]};
  return {command,description:'Execute the deterministic fixture task operation'};
}
function miniCompletion(body,tool,call) {
  return !call && tool?.name==='bash' && JSON.stringify(body.messages??body.input??[]).includes('COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT');
}
function sendSse(res, rows, done=false) {
  res.writeHead(200,{'content-type':'text/event-stream','cache-control':'no-cache'});
  for (const row of rows) {
    if (row.type) res.write(`event: ${row.type}\n`);
    res.write(`data: ${JSON.stringify(row)}\n\n`);
  }
  if(done)res.write('data: [DONE]\n\n');
  res.end();
}
export function validateRequest(body, route) {
  if (body.model === 'gpt-6.1-sol' && route !== '/v1/responses') throw new Error('GPT6.1 Sol tool loop requires Responses');
  if (body.model === 'gpt-6.1-sol' && ['temperature','top_p','logprobs'].some(key => key in body)) throw new Error('Unsupported Sol reasoning request parameter');
  if (body.model === 'claude-sonnet-5-5') {
    if (['temperature','top_p','top_k'].some(key => key in body)) throw new Error('Sonnet5.5 rejects sampling parameters');
    if (body.thinking && !['adaptive','between_tools'].includes(body.thinking.type)) throw new Error('Sonnet5.5 requires adaptive/between_tools thinking');
    if (body.thinking && 'budget_tokens' in body.thinking) throw new Error('Sonnet5.5 rejects thinking budgets');
    if (['any','tool'].includes(body.tool_choice?.type)) throw new Error('Sonnet5.5 rejects forced tool choice');
    const messages = body.messages ?? [];
    if (messages.some(m => Array.isArray(m.content) && m.content.some(c => c.type === 'tool_result'))) {
      const preserved = messages.some(m => Array.isArray(m.content) && m.content.some(c => c.type === 'thinking' && c.thinking === '' && c.signature === 'fixture-thinking-signature'));
      if (!preserved) throw new Error('Empty signed thinking block was dropped from tool replay');
    }
  }
}
function anthropic(body,res,tool,call,turn) {
  const usage={input_tokens:100,output_tokens:20,cache_creation_input_tokens:0,cache_read_input_tokens:0};
  const block=tool&&call?{type:'tool_use',id:'fixture-tool-1',name:tool.name,input:argsFor(tool)}:{type:'text',text:'Fixture task complete.'};
  const message={id:'msg_fixture_'+turn,type:'message',role:'assistant',model:body.model,content:[...(body.model==='claude-sonnet-5-5'?[{type:'thinking',thinking:'',signature:'fixture-thinking-signature'}]:[]),block],stop_reason:tool&&call?'tool_use':'end_turn',stop_sequence:null,usage};
  if(!body.stream){res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify(message));return;}
  const empty=block.type==='tool_use'?{...block,input:{}}:{...block,text:''};
  const thinking = body.model==='claude-sonnet-5-5';
  const first = thinking ? [{type:'content_block_start',index:0,content_block:{type:'thinking',thinking:''}}, {type:'content_block_delta',index:0,delta:{type:'signature_delta',signature:'fixture-thinking-signature'}},{type:'content_block_stop',index:0}] : [];
  const index = thinking ? 1 : 0;
  sendSse(res,[{type:'message_start',message:{...message,content:[],stop_reason:null,usage:{...usage,output_tokens:0}}},
    ...first, {type:'content_block_start',index,content_block:empty},
    {type:'content_block_delta',index,delta:block.type==='tool_use'?{type:'input_json_delta',partial_json:JSON.stringify(block.input)}:{type:'text_delta',text:block.text}},
    {type:'content_block_stop',index},{type:'message_delta',delta:{stop_reason:message.stop_reason,stop_sequence:null},usage:{output_tokens:20}},
    {type:'message_stop'}]);
}
function responses(body,res,tool,call,turn) {
  const complete=miniCompletion(body,tool,call);
  let item=tool&&(call||complete)?{type:'function_call',id:'fc_fixture_'+turn,call_id:'call_fixture_'+turn,name:tool.name,arguments:JSON.stringify(argsFor(tool,complete?'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT':toolCommand)),status:'completed'}:
    {type:'message',id:'msg_fixture',status:'completed',role:'assistant',content:[{type:'output_text',text:'Fixture task complete.',annotations:[]}]};
  if (tool?.type==='custom' && tool?.name==='exec' && call) {
    item.type='custom_tool_call'; item.name='exec'; item.namespace=tool.namespace; item.input='const result=await tools.exec_command({cmd:'+JSON.stringify(toolCommand)+'});text(result);'; delete item.arguments;
  }
  const response={id:'resp_fixture_'+turn,object:'response',created_at:1,status:'completed',model:body.model,output:[item],usage:{input_tokens:100,output_tokens:20,total_tokens:120,input_tokens_details:{cached_tokens:0},output_tokens_details:{reasoning_tokens:0}}};
  if(!body.stream){res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify(response));return;}
  const rows=[{type:'response.created',response:{...response,status:'in_progress',output:[]}},
    {type:'response.in_progress',response:{...response,status:'in_progress',output:[]}},
    {type:'response.output_item.added',output_index:0,item:{...item,status:'in_progress',...(item.type==='function_call'?{arguments:''}:{content:[]})}}];
  if(item.type==='custom_tool_call')rows.push({type:'response.custom_tool_call_input.delta',item_id:item.id,output_index:0,delta:item.input},{type:'response.custom_tool_call_input.done',item_id:item.id,output_index:0,input:item.input});
  else if(item.type==='function_call')rows.push({type:'response.function_call_arguments.delta',item_id:item.id,output_index:0,delta:item.arguments},
    {type:'response.function_call_arguments.done',item_id:item.id,output_index:0,arguments:item.arguments});
  else rows.push({type:'response.content_part.added',item_id:item.id,output_index:0,content_index:0,part:{type:'output_text',text:'',annotations:[]}},
    {type:'response.output_text.delta',item_id:item.id,output_index:0,content_index:0,delta:item.content[0].text},
    {type:'response.output_text.done',item_id:item.id,output_index:0,content_index:0,text:item.content[0].text},
    {type:'response.content_part.done',item_id:item.id,output_index:0,content_index:0,part:item.content[0]});
  rows.push({type:'response.output_item.done',output_index:0,item},{type:'response.completed',response});
  sendSse(res,rows.map((row,i)=>({...row,sequence_number:i})));
}
function chat(body,res,tool,call,turn) {
  const complete=miniCompletion(body,tool,call);
  const message=tool&&(call||complete)?{role:'assistant',content:null,tool_calls:[{id:'call_fixture_'+turn,type:'function',function:{name:tool.name,arguments:JSON.stringify(argsFor(tool,complete?'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT':toolCommand))}}]}:
    {role:'assistant',content:tool?'Fixture task complete.':`\`\`\`bash\n${call?toolCommand:'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'}\n\`\`\``};
  const data={id:'chat_fixture_'+turn,object:'chat.completion',created:1,model:body.model,choices:[{index:0,message,finish_reason:message.tool_calls?'tool_calls':'stop'}],usage:{prompt_tokens:100,completion_tokens:20,total_tokens:120}};
  if(!body.stream){res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify(data));return;}
  sendSse(res,[{...data,object:'chat.completion.chunk',choices:[{index:0,delta:message,finish_reason:null}]},
    {...data,object:'chat.completion.chunk',choices:[{index:0,delta:{},finish_reason:message.tool_calls?'tool_calls':'stop'}]}],true);
}
export function createFixtureServer(log = '/logs/agent/mock-requests.jsonl') {
let turn = 0;
let toolIssued = false;
return http.createServer(async(req,res)=>{
  if(req.method==='GET'){res.writeHead(200,{'content-type':'application/json'});res.end('{"ok":true,"data":[]}');return;}
  let text='';for await(const part of req){text+=part;if(text.length>8*1024*1024){res.writeHead(413);res.end();return;}}
  try{
    const body=JSON.parse(text); const tool=chosenTool(body);
    const route=new URL(req.url,'http://127.0.0.1').pathname;
    if(!['/v1/messages','/v1/messages/count_tokens','/v1/responses','/v1/chat/completions'].includes(route)){
      res.writeHead(404);res.end('{"error":{"message":"unsupported fixture route"}}');return;
    }
    fs.appendFileSync(log,JSON.stringify({path:req.url,model:body.model,stream:body.stream??false,tool_names:(body.tools??[]).map(t=>(t.function??t).name),request_keys:Object.keys(body),tool_definitions:body.tools??body.toolsets??body.tool_groups,settings:{reasoning:body.reasoning,reasoning_effort:body.reasoning_effort,thinking:body.thinking,output_config:body.output_config,max_tokens:body.max_tokens,max_output_tokens:body.max_output_tokens,temperature:body.temperature,tool_choice:body.tool_choice},messages:body.messages??body.input??[],synthetic_usage:true})+'\n');
    try { validateRequest(body,route); } catch (error) { fs.appendFileSync(log.replace('mock-requests','mock-rejections'),JSON.stringify({model:body.model,error:String(error)})+'\n'); throw error; }
    if(route==='/v1/messages/count_tokens'){res.writeHead(200,{'content-type':'application/json'});res.end('{"input_tokens":100}');return;}
    turn++;if(turn>16){res.writeHead(429);res.end('{"error":{"message":"fixture request bound exceeded"}}');return;}
    // OpenCode sends a title request without tools before the task request.
    // Only a task-capable request consumes the one fixture tool operation.
    const call=!toolIssued && (Boolean(tool) || route==='/v1/chat/completions');
    if(call)toolIssued=true;
    if(route==='/v1/messages')anthropic(body,res,tool,call,turn);
    else if(route==='/v1/responses')responses(body,res,tool,call,turn);
    else if(route==='/v1/chat/completions')chat(body,res,tool,call,turn);
  }catch(error){res.writeHead(400);res.end(JSON.stringify({error:{message:String(error)}}));}
});
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  createFixtureServer().listen(8768,'127.0.0.1');
}
