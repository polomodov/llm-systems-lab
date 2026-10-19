// Public synthetic fixtures; no model weights, API keys or hidden tasks.
export const deployment=()=>({schema_version:1,kind:'local-llama-cpp',endpoint:{host:'127.0.0.1',port:18080,transport:'http'},alias:'lab-model',model:{repository:'synthetic/fixture',revision:'a'.repeat(40),format:'GGUF',quantization:'synthetic-Q6_K',files:[{path:'/synthetic/model.gguf',bytes:1,sha256:'b'.repeat(64)}],tokenizer_sha256:'c'.repeat(64),chat_template_sha256:'d'.repeat(64)},engine:{id:'llama-cpp',version:'fixture-1',commit:'e'.repeat(40),backend:'metal',build_flags:['synthetic'],executable:'/synthetic/llama-server',files:[{path:'/synthetic/llama-server',bytes:1,sha256:'f'.repeat(64)}]},hardware:{id:'synthetic-mac',passport:{path:'/synthetic/passport',bytes:1,sha256:'a'.repeat(64)},driver:'synthetic',power_mode:0},protocol:{context_tokens:8192,output_tokens:2048,temperature:0,seed:1,top_p:1,reasoning:'auto',thinking:true,kv:['f16','f16'],batch:512,ubatch:256,threads:8,slots:1,offload:999,prefix_cache:false,tool_protocol:'openai-chat'}});
export const request=()=>({model:'lab-model',messages:[{role:'user',content:'Synthetic bridge test'}],stream:true,stream_options:{include_usage:true},max_tokens:2048,temperature:0,seed:1,top_p:1,parallel_tool_calls:false});
export function stream({tool=false,usage=true,model='lab-model'}={}) {
  const chunk=(delta,finish_reason=null)=>({id:'synthetic-completion',object:'chat.completion.chunk',created:1,model,choices:[{index:0,delta,finish_reason}]});
  const rows=[chunk({role:'assistant',content:''})];
  if(tool) {
    rows.push(chunk({tool_calls:[{index:0,id:'call_bridge_1',type:'function',function:{name:'bash',arguments:'{"command":'}}]}));
    rows.push(chunk({tool_calls:[{index:0,function:{arguments:'"printf BRIDGE_TOOL_READY"}'}}]}));rows.push(chunk({},'tool_calls'));
  }else{rows.push(chunk({content:'BRIDGE_FINAL'}));rows.push(chunk({},'stop'));}
  if(usage)rows.push({id:'synthetic-completion',object:'chat.completion.chunk',created:1,model,choices:[],usage:{prompt_tokens:20,completion_tokens:10,total_tokens:30}});
  return rows.map(row=>'data: '+JSON.stringify(row)+'\n\n').join('')+'data: [DONE]\n\n';
}
