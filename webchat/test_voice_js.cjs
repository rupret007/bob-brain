const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, 'static/voice.js'), 'utf8');
const pause = () => new Promise(resolve => setImmediate(resolve));
const interruptionAcknowledged = require('./voice_interruption_controls.cjs');
function interruptionProof(options = {}) {
  const events=[
    {seq:10,kind:'interrupted',counts:{interruptions:1,outputAudio:20}},
    {seq:11,kind:'generation_complete',counts:{interruptions:1,outputAudio:25}},
    {seq:12,kind:'turn_complete',counts:{interruptions:1,outputAudio:25}}];
  const sample={before:{interruptions:0,stops:0,requests:1,replies:1},
    proof:{stops:1,starts:8,startsAtInterruption:7},events,
    requests:['You: Earlier request','You: Stop. Just say okay.'],replies:['Bob: Earlier answer','Bob: Okay.']};
  options.mutate?.(sample);
  return vm.runInNewContext('('+interruptionAcknowledged.toString()+')(before)',{
    before:sample.before,window:{voiceProof:sample.proof,voiceEvents:{snapshot:()=>({events:sample.events})}},
    document:{querySelectorAll:selector=>(selector==='.call-you'?sample.requests:sample.replies).map(textContent=>({textContent}))}});
}
test('voice interruption proof accepts fresh completed audio acknowledgment with native spelling/name omission',()=>{
  assert.equal(interruptionProof(),true);
  assert.equal(interruptionProof({mutate:s=>{s.requests[1]='You: Stop. Just say okay Jeff.';s.replies[1]='Bob: OK, Jeff!';}}),true);
});
for(const [name,mutate] of [
  ['stale acknowledgment',s=>{s.replies=['Bob: Okay.'];}],
  ['no new request',s=>{s.requests=['You: Stop. Just say okay.'];}],
  ['no new audio',s=>{s.events.slice(1).forEach(e=>{e.counts.outputAudio=20;});}],
  ['incomplete reply',s=>{s.events.pop();}],
  ['no completed generation',s=>{s.events.splice(1,1);}],
  ['completion preceding interruption',s=>{s.events[1].seq=8;s.events[2].seq=9;}],
  ['continued story',s=>{s.replies[1]='Bob: Okay. The sailor continued toward the horizon.';}],
  ['unrelated request',s=>{s.requests[1]='You: What is next?';}],
  ['recognized name ignored',s=>{s.requests[1]='You: Stop. Just say okay Jeff.';}],
  ['playback never stopped',s=>{s.proof.stops=0;}],
  ['new audio never played',s=>{s.proof.starts=7;}],
  ['no new interruption',s=>{s.events[0].counts.interruptions=0;}],
]) test('voice interruption proof rejects '+name,()=>assert.equal(interruptionProof({mutate}),false));
function deferred() { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b; }); return {promise,resolve,reject}; }
function fixture(options = {}) {
  const states=[], requests=[], sockets=[], contexts=[], tracks=[];
  const track = { stopped:false, stop(){this.stopped=true;}, addEventListener(){} }; tracks.push(track);
  const stream = {getTracks:()=>[track]};
  class Node { connect(){return this;} disconnect(){this.disconnected=true;} }
  class Context {
    constructor(){this.state='suspended';this.currentTime=0;this.audioWorklet={addModule:async()=>{}};this.destination={};contexts.push(this);}
    resume(){this.state='running';return Promise.resolve();}
    close(){this.state='closed';return Promise.resolve();}
    createMediaStreamSource(){return new Node();}
    createGain(){return Object.assign(new Node(),{gain:{value:1}});}
    createBuffer(channels,n,rate){return {duration:n/rate,getChannelData:()=>new Float32Array(n)};}
    createBufferSource(){return Object.assign(new Node(),{start(){this.started=true;},stop(){this.stopped=true;}});}
  }
  class Socket {
    static OPEN=1;
    constructor(){this.readyState=1;this.bufferedAmount=0;this.sent=[];sockets.push(this);}
    send(raw){this.sent.push(JSON.parse(raw));}
    close(){this.closed=true;this.readyState=3;}
  }
  class Worklet extends Node { constructor(){super();this.port={};} }
  const window={isSecureContext:true,AudioContext:Context,AudioWorkletNode:Worklet,WebSocket:Socket};
  const context={window,navigator:{mediaDevices:{getUserMedia:options.getUserMedia || (async()=>stream)}},
    AudioContext:Context,AudioWorkletNode:Worklet,WebSocket:Socket,crypto,setTimeout,clearTimeout,setInterval,clearInterval,
    ...options.clock,
    TextDecoder,TextEncoder,Uint8Array,ArrayBuffer,DataView,atob,btoa};
  vm.runInNewContext(code,context);
  const controller = new window.BobVoice({api:async(route,data)=>{
    requests.push({route,data});
    if(options.api) return options.api(route,data);
    if(route.endsWith('/start'))return {call_id:'fixture',url:'wss://example.test',token:'auth_tokens/test',model:'models/test',expires_at:Date.now()/1000+600};
    return {ok:true,settled:true};
  },onState:(text,phase)=>states.push({text,phase}),onTranscript:()=>{},onSaved:()=>{}});
  return {controller,window,states,requests,sockets,contexts,tracks,stream};
}
test('reject insecure contexts without requesting a microphone',async()=>{
  const f=fixture();f.window.isSecureContext=false;await f.controller.start('chat');
  assert.equal(f.contexts.length,0);assert.match(f.states.at(-1).text,/HTTPS/);
});
test('permission denial releases audio and allows retry',async()=>{
  const f=fixture({getUserMedia:async()=>{throw Object.assign(new Error(),{name:'NotAllowedError'});}});
  await f.controller.start('chat');await pause();
  assert.equal(f.controller.active,false);assert.equal(f.contexts[0].state,'closed');assert.match(f.states.at(-1).text,/Microphone blocked/);
});
test('known prepaid-credit close explains recovery without exposing provider details or retrying',async()=>{
  const f=fixture();await f.controller.start('chat');
  f.sockets[0].onclose({code:1011,reason:'Your prepayment credits are depleted. private-account-marker https://private.example/secret'});
  await pause();
  assert.match(f.states.at(-1).text,/prepaid credits.*Google AI Studio/);
  assert.doesNotMatch(f.states.at(-1).text,/private|secret|https:/);
  assert.equal(f.states.at(-1).phase,'error');assert.equal(f.controller.active,false);
  assert.equal(f.sockets[0].closed,true);assert.equal(f.tracks[0].stopped,true);assert.equal(f.contexts[0].state,'closed');
  assert.equal(f.requests.filter(r=>r.route.endsWith('/start')).length,1);
  assert.equal(f.requests.filter(r=>r.route.endsWith('/end')).length,1);
});
test('unknown close reasons and other codes retain a generic safe message',async()=>{
  for(const event of [{code:1011,reason:'private-account-marker'},
                     {code:1008,reason:'Your prepayment credits are depleted.'},undefined]) {
    const f=fixture();await f.controller.start('chat');f.sockets[0].onclose(event);await pause();
    assert.equal(f.states.at(-1).text,'Call disconnected. Return to chat to start another call.');
    assert.equal(f.controller.active,false);assert.equal(f.sockets.length,1);
  }
});
test('hanging up during microphone permission stops a late stream',async()=>{
  const mic=deferred(),f=fixture({getUserMedia:()=>mic.promise});
  const starting=f.controller.start('chat');await f.controller.stop();mic.resolve(f.stream);await starting;
  assert.equal(f.tracks[0].stopped,true);assert.equal(f.sockets.length,0);
});
test('hangup handles a rejected audio resume while microphone permission is pending',async()=>{
  const mic=deferred(),resume=deferred(),f=fixture({getUserMedia:()=>mic.promise});
  f.window.AudioContext.prototype.resume=()=>resume.promise;
  const starting=f.controller.start('chat');await f.controller.stop();
  resume.reject(Object.assign(new Error('Audio context closed'),{name:'InvalidStateError'}));
  await pause();mic.resolve(f.stream);await starting;await pause();
  assert.equal(f.controller.active,false);assert.equal(f.tracks[0].stopped,true);
  assert.equal(f.sockets.length,0);assert.equal(f.requests.length,0);
  assert.equal(f.states.at(-1).phase,'ended');
});
test('audio startup rejection stays handled and reports audio rather than microphone denial',async()=>{
  const mic=deferred(),resume=deferred(),f=fixture({getUserMedia:()=>mic.promise});
  f.window.AudioContext.prototype.resume=()=>resume.promise;
  const starting=f.controller.start('chat');
  resume.reject(Object.assign(new Error('Private low-level detail'),{name:'NotAllowedError'}));
  await pause();mic.resolve(f.stream);await starting;await pause();
  assert.equal(f.controller.active,false);assert.equal(f.tracks[0].stopped,true);
  assert.equal(f.contexts[0].state,'closed');assert.equal(f.requests.length,0);
  assert.match(f.states.at(-1).text,/Audio could not start/);
  assert.doesNotMatch(f.states.at(-1).text,/Microphone blocked|Private low-level detail/);
});
test('late startup resume after hangup cannot load a worklet or open a provider',async()=>{
  const resume=deferred(),f=fixture();
  f.window.AudioContext.prototype.resume=()=>resume.promise;
  const starting=f.controller.start('chat');await pause();
  let modules=0;f.contexts[0].audioWorklet.addModule=async()=>{modules++;};
  await f.controller.stop();resume.resolve();await starting;
  assert.equal(modules,0);assert.equal(f.requests.length,0);assert.equal(f.tracks[0].stopped,true);
});
test('hanging up while token request is pending ends that late session',async()=>{
  const token=deferred();const f=fixture({api:async(route)=>route.endsWith('/start')?token.promise:{ok:true,settled:true}});
  const starting=f.controller.start('chat');await pause();await f.controller.stop();
  token.resolve({call_id:'late',expires_at:Date.now()/1000+600});await starting;
  assert.equal(f.sockets.length,0);assert.equal(f.requests.at(-1).route,'/api/voice/end');
});
test('setup gates microphone packets and PCM streams over WebSocket',async()=>{
  const f=fixture();await f.controller.start('chat');const s=f.controller.session;
  s.capture.port.onmessage({data:new ArrayBuffer(3200)});assert.equal(f.sockets[0].sent.length,0);
  f.controller.event(s,{setupComplete:{}});s.capture.port.onmessage({data:new ArrayBuffer(3200)});
  assert.equal(f.sockets[0].sent[0].realtimeInput.audio.mimeType,'audio/pcm;rate=16000');await f.controller.stop();
});
test('barge-in stops every queued source immediately and marks interrupted transcript',async()=>{
  const f=fixture();await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{setupComplete:{}});
  f.controller.event(s,{serverContent:{inputTranscription:{text:'Hello'},outputTranscription:{text:'Hello Jeff'}}});
  f.controller.play(s,{data:btoa('\0'.repeat(4800)),mimeType:'audio/pcm;rate=24000'});
  f.controller.play(s,{data:btoa('\0'.repeat(4800)),mimeType:'audio/pcm;rate=24000'});
  const sources=[...s.sources];assert.equal(sources.length,2);
  f.controller.event(s,{serverContent:{interrupted:true}});
  assert.ok(sources.every(source=>source.stopped));assert.equal(s.sources.size,0);assert.equal(s.nextAudio,0);
  assert.ok([...s.entries.values()].some(row=>row.role==='assistant'&&row.interrupted));await f.controller.stop();
});
test('hangup releases microphone socket nodes timers and output',async()=>{
  const f=fixture();await f.controller.start('chat');const s=f.controller.session;
  await f.controller.stop();assert.equal(f.tracks[0].stopped,true);assert.equal(s.socket.closed,true);
  assert.equal(s.capture.disconnected,true);assert.equal(s.audio.state,'closed');assert.equal(s.socket.onmessage,null);
});
test('a requested long reply buffers sixty seconds and barge-in stops all of it',async t=>{
  const f=fixture();t.after(()=>f.controller.stop());await f.controller.start('chat');const s=f.controller.session;
  const chunk={data:btoa('\0'.repeat(48000)),mimeType:'audio/pcm;rate=24000'};
  for(let n=0;n<60;n++)f.controller.play(s,chunk);
  assert.equal(f.controller.active,true);assert.equal(s.sources.size,60);
  const sources=[...s.sources];f.controller.event(s,{serverContent:{interrupted:true}});
  assert.ok(sources.every(source=>source.stopped&&source.disconnected));
  assert.equal(s.sources.size,0);assert.equal(s.nextAudio,0);
  f.controller.play(s,chunk);assert.equal(s.sources.size,1);
});
test('audio queue counts full chunk duration and fails safely at the finite limit',async t=>{
  const f=fixture();t.after(()=>f.controller.stop());await f.controller.start('chat');const s=f.controller.session;
  const chunk={data:btoa('\0'.repeat(48000)),mimeType:'audio/pcm;rate=24000'};
  for(let n=0;n<119;n++)f.controller.play(s,chunk);
  assert.equal(s.sources.size,119);
  const sources=[...s.sources];let buffers=0;
  s.audio.createBuffer=()=>{buffers++;throw new Error('Must reject before allocating another audio buffer');};
  s.socket.onmessage({data:JSON.stringify({serverContent:{modelTurn:{parts:[{inlineData:chunk}]}}})});
  await pause();assert.equal(buffers,0);
  assert.equal(f.controller.active,false);assert.equal(s.socket.closed,true);assert.equal(f.tracks[0].stopped,true);
  assert.ok(sources.every(source=>source.stopped&&source.disconnected));
  assert.match(f.states.at(-1).text,/reply exceeded.*audio buffer/i);
  assert.equal(f.requests.filter(r=>r.route.endsWith('/start')).length,1);
});
test('slow network closes streaming instead of accumulating delayed speech',async()=>{
  const f=fixture();await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{setupComplete:{}});s.socket.bufferedAmount=128001;
  s.capture.port.onmessage({data:new ArrayBuffer(3200)});await pause();
  assert.equal(f.controller.active,false);assert.match(f.states.at(-1).text,/too slow/);
});
test('transcript retry retains dirty data and uses one flusher',async()=>{
  let failing=true;
  const f=fixture({api:async(route)=>{
    if(route.endsWith('/start'))return {call_id:'fixture',url:'wss://example',token:'token',expires_at:Date.now()/1000+600};
    if(route.endsWith('/transcript')&&failing)throw new Error('offline');
    return {ok:true,settled:true};
  }});
  await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{serverContent:{inputTranscription:{text:'Please keep this'}}});
  await f.controller.save(s);assert.equal(f.controller.pending.length,1);assert.equal(f.states.at(-1).phase,'unsaved');
  failing=false;await f.controller.retrySave();assert.equal(f.controller.pending.length,0);await f.controller.stop();
});
test('long calls save every turn within server row and UTF-8 keepalive limits',async()=>{
  const f=fixture();
  const entries=Array.from({length:120},(_,i)=>({turn_id:crypto.randomUUID(),role:i%2?'assistant':'user',order:i,
    content:i<80?'A short spoken turn.':'船'.repeat(700),version:1}));
  f.controller.pending.push({call_id:'fixture',entries});
  await f.controller.flush();
  const requests=f.requests.filter(r=>r.route.endsWith('/transcript'));
  assert.ok(requests.length>3);
  assert.ok(requests.every(r=>r.data.entries.length<=40 && Buffer.byteLength(JSON.stringify(r.data))<49000));
  assert.deepEqual(requests.flatMap(r=>Array.from(r.data.entries)),entries);
  assert.equal(f.controller.pending.length,0);
});
test('tool dispatch takes saved spoken turn, never model arguments',async()=>{
  const f=fixture({api:async(route)=>{
    if(route.endsWith('/start'))return {call_id:'fixture',url:'wss://example',token:'token',expires_at:Date.now()/1000+600};
    if(route.endsWith('/tool'))return {request_id:'r',conversation:{messages:[{role:'assistant',request_id:'r',status:'done',content:'Queued — job test.'}]}};
    return {ok:true,settled:true};
  }});
  await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{serverContent:{inputTranscription:{text:'start a job: test widget'}}});
  s.inputTurn.lastInputAt=0;
  await f.controller.tool(s,{id:'tool1',name:'ask_bob',args:{message:'merge main'}});
  const request=f.requests.find(r=>r.route.endsWith('/tool'));
  assert.deepEqual(Object.keys(request.data).sort(),['call_id','turn_id']);
  assert.equal(request.data.turn_id,s.inputTurn.id);assert.match(s.socket.sent.at(-1).toolResponse.functionResponses[0].response.result,/Queued/);
  await f.controller.stop();
});
test('cancelled tools cannot dispatch or speak after a barge-in',async()=>{
  const f=fixture();await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{serverContent:{inputTranscription:{text:'status'}}});s.inputTurn.lastInputAt=0;
  s.cancelledTools.add('cancelled');await f.controller.tool(s,{id:'cancelled',name:'ask_bob'});
  assert.equal(f.requests.filter(r=>r.route.endsWith('/tool')).length,0);await f.controller.stop();
});
test('old audio and completion callbacks cannot hide a pending tool',async t=>{
  const dispatched=deferred();
  const f=fixture({api:async route=>{
    if(route.endsWith('/start'))return {call_id:'fixture',url:'wss://example',token:'token',expires_at:Date.now()/1000+600};
    if(route.endsWith('/tool'))return dispatched.promise;
    return {ok:true,settled:true};
  }});
  t.after(()=>f.controller.stop());await f.controller.start('chat');const s=f.controller.session;
  f.controller.play(s,{data:btoa('\0'.repeat(4800)),mimeType:'audio/pcm;rate=24000'});
  const source=[...s.sources][0];
  f.controller.event(s,{serverContent:{inputTranscription:{text:'Tell me a long story'}}});
  s.inputTurn.lastInputAt=0;
  const work=f.controller.tool(s,{id:'pending',name:'ask_bob'});await pause();
  assert.equal(s.pendingTools.size,1);assert.equal(f.states.at(-1).phase,'thinking');
  source.onended();assert.equal(f.states.at(-1).phase,'thinking');
  f.controller.event(s,{serverContent:{turnComplete:true}});
  assert.equal(f.states.at(-1).phase,'thinking');
  await f.controller.retrySave();assert.equal(f.states.at(-1).phase,'thinking');
  s.audio.state='suspended';s.audio.onstatechange();assert.equal(f.states.at(-1).phase,'paused');
  await f.controller.resume();assert.equal(f.states.at(-1).phase,'thinking');
  dispatched.resolve({request_id:'r',conversation:{messages:[{role:'assistant',request_id:'r',status:'done',content:'A sailor found a compass.'}]}});
  await work;assert.equal(s.pendingTools.size,0);
  f.controller.play(s,{data:btoa('\0'.repeat(4800)),mimeType:'audio/pcm;rate=24000'});
  assert.equal(f.states.at(-1).phase,'speaking');
  [...s.sources][0].onended();assert.equal(f.states.at(-1).phase,'listening');
});
for(const ending of ['cancel','hangup','remote-close'])test(`pending voice state clears on ${ending} and rejects late tool speech`,async t=>{
  const dispatched=deferred();
  const f=fixture({api:async route=>{
    if(route.endsWith('/start'))return {call_id:'fixture',url:'wss://example',token:'token',expires_at:Date.now()/1000+600};
    if(route.endsWith('/tool'))return dispatched.promise;
    return {ok:true,settled:true};
  }});
  t.after(()=>f.controller.stop());await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{serverContent:{inputTranscription:{text:'Tell me a long story'}}});s.inputTurn.lastInputAt=0;
  const work=f.controller.tool(s,{id:'pending',name:'ask_bob'});await pause();
  assert.equal(s.pendingTools.size,1);
  if(ending==='cancel'){
    f.controller.event(s,{toolCallCancellation:{ids:['pending']}});
    assert.equal(f.states.at(-1).phase,'thinking','server cancellation has not settled yet');
    await pause();
  }
  else if(ending==='remote-close') { s.socket.onclose({code:1011,reason:'Internal error'});await pause(); }
  else await f.controller.stop();
  assert.equal(s.pendingTools.size,0);
  const phase=f.states.at(-1).phase;
  assert.equal(phase,ending==='cancel'?'listening':ending==='remote-close'?'error':'ended');
  dispatched.resolve({request_id:'r',conversation:{messages:[{role:'assistant',request_id:'r',status:'done',content:'Late result'}]}});
  await work;
  assert.equal(s.socket.sent.filter(m=>m.toolResponse).length,0);
  assert.equal(f.states.at(-1).phase,phase);
  if(ending==='remote-close'){
    assert.equal(f.tracks[0].stopped,true);assert.equal(s.audio.state,'closed');
    assert.equal(f.requests.filter(r=>r.route.endsWith('/start')).length,1);
    assert.equal(f.requests.filter(r=>r.route.endsWith('/end')).length,1);
  }
});
test('waiting voice reply is interrupted before a newer version request and waits for worker exit',async t=>{
  const stopped=deferred();let toolCount=0,interruptCount=0;
  const f=fixture({api:async(route,data)=>{
    if(route.endsWith('/start'))return {call_id:'fixture',url:'wss://example',token:'token',expires_at:Date.now()/1000+600};
    if(route.endsWith('/tool')){
      toolCount++;const id='r'+toolCount;
      return {request_id:id,conversation:{messages:[{role:'assistant',request_id:id,
        status:toolCount===1?'waiting':'done',content:toolCount===1?'The provider could not complete this reply.':'Web Bob version 1234567'}]}};
    }
    if(route.endsWith('/interrupt'))return ++interruptCount===1?{ok:true,settled:false}:stopped.promise;
    return {ok:true,settled:true};
  }});
  t.after(()=>f.controller.stop());await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{serverContent:{inputTranscription:{text:'Tell me a long story'}}});
  s.inputTurn.lastInputAt=0;const old=s.inputTurn;
  await f.controller.tool(s,{id:'story',name:'ask_bob'});
  f.controller.event(s,{serverContent:{outputTranscription:{text:'The story is waiting.'}}});
  f.controller.play(s,{data:btoa('\0'.repeat(4800)),mimeType:'audio/pcm;rate=24000'});
  f.controller.event(s,{serverContent:{turnComplete:true}});
  f.controller.event(s,{serverContent:{inputTranscription:{text:'What version are you running?'}}});
  s.inputTurn.lastInputAt=0;const next=s.inputTurn;
  assert.notEqual(old.id,next.id);
  f.controller.event(s,{serverContent:{interrupted:true}});
  const work=f.controller.tool(s,{id:'version',name:'ask_bob'});
  await pause();assert.equal(toolCount,1);
  assert.equal(f.requests.find(r=>r.route.endsWith('/interrupt')).data.turn_id,old.id);
  assert.equal(s.cancelledTools.has('version'),false);
  await new Promise(resolve=>setTimeout(resolve,400));assert.equal(toolCount,1);
  stopped.resolve({ok:true,settled:true});await work;
  assert.equal(toolCount,2);assert.equal(s.interruptions.size,0);
  assert.equal(f.requests.filter(r=>r.route.endsWith('/tool')).at(-1).data.turn_id,next.id);
  assert.match(s.socket.sent.at(-1).toolResponse.functionResponses[0].response.result,/Web Bob/);
});
test('interruption before tool admission saves and cancels that turn without starting it',async t=>{
  const saved=deferred();
  const f=fixture({api:async route=>{
    if(route.endsWith('/start'))return {call_id:'fixture',url:'wss://example',token:'token',expires_at:Date.now()/1000+600};
    if(route.endsWith('/transcript'))return saved.promise;
    return {ok:true,settled:true};
  }});
  t.after(()=>f.controller.stop());await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{serverContent:{inputTranscription:{text:'Tell me a long story'}}});s.inputTurn.lastInputAt=0;
  const turn=s.inputTurn.id,work=f.controller.tool(s,{id:'story',name:'ask_bob'});
  await pause();f.controller.event(s,{serverContent:{interrupted:true}});
  saved.resolve({ok:true});await work;await f.controller.flushInterruptions(s);
  assert.equal(f.requests.filter(r=>r.route.endsWith('/tool')).length,0);
  assert.equal(f.requests.find(r=>r.route.endsWith('/interrupt')).data.turn_id,turn);
  assert.equal(s.socket.sent.filter(m=>m.toolResponse).length,0);
});
test('failed interruption blocks later tools until explicit save recovery confirms cancellation',async t=>{
  let failing=true,toolCount=0;
  const f=fixture({api:async route=>{
    if(route.endsWith('/start'))return {call_id:'fixture',url:'wss://example',token:'token',expires_at:Date.now()/1000+600};
    if(route.endsWith('/interrupt')&&failing)throw new Error('Cancellation could not be confirmed.');
    if(route.endsWith('/tool')){
      const id='r'+(++toolCount);
      return {request_id:id,conversation:{messages:[{role:'assistant',request_id:id,status:'waiting',content:'Reply queued.'}]}};
    }
    return {ok:true,settled:true};
  }});
  t.after(()=>f.controller.stop());await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{serverContent:{inputTranscription:{text:'Tell me a story'}}});s.inputTurn.lastInputAt=0;
  await f.controller.tool(s,{id:'story',name:'ask_bob'});
  f.controller.event(s,{serverContent:{outputTranscription:{text:'Reply queued.'},interrupted:true}});
  // The interrupted output may arrive in a separate event from its transcript.
  f.controller.event(s,{serverContent:{interrupted:true}});await pause();
  assert.equal(f.states.at(-1).phase,'unsaved');assert.equal(s.interruptions.size,1);
  f.controller.event(s,{serverContent:{turnComplete:true}});
  assert.equal(f.states.at(-1).phase,'unsaved','turn completion must retain Retry save');
  f.controller.play(s,{data:btoa('\0'.repeat(4800)),mimeType:'audio/pcm;rate=24000'});
  assert.equal(f.states.at(-1).phase,'unsaved','speaking must retain Retry save');
  [...s.sources][0].onended();
  assert.equal(f.states.at(-1).phase,'unsaved','audio completion must retain Retry save');
  s.audio.state='suspended';s.audio.onstatechange();
  assert.equal(f.states.at(-1).phase,'unsaved','cancellation recovery precedes audio resume');
  f.controller.event(s,{serverContent:{inputTranscription:{text:'What version are you running?'}}});s.inputTurn.lastInputAt=0;
  await f.controller.tool(s,{id:'version',name:'ask_bob'});assert.equal(toolCount,1);
  assert.equal(f.states.at(-1).phase,'unsaved','a failed new tool must retain Retry save');
  assert.match(f.states.at(-1).text,/earlier reply.*Retry save/);
  failing=false;await f.controller.retrySave();assert.equal(s.interruptions.size,0);
  assert.equal(s.interruptionError,false);assert.equal(f.states.at(-1).phase,'paused');
  await f.controller.resume();assert.equal(f.states.at(-1).phase,'listening');
  await f.controller.tool(s,{id:'version-retry',name:'ask_bob'});assert.equal(toolCount,2);
});
test('remote close persists a partially spoken reply as interrupted and releases queued audio',async()=>{
  const f=fixture();await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{serverContent:{inputTranscription:{text:'Tell me a story'},outputTranscription:{text:'The sailor found'}}});
  f.controller.play(s,{data:btoa('\0'.repeat(4800)),mimeType:'audio/pcm;rate=24000'});
  const sources=[...s.sources];s.socket.onclose({code:1011,reason:'Internal error'});await pause();
  assert.ok(sources.every(source=>source.stopped&&source.disconnected));
  const saved=f.requests.filter(r=>r.route.endsWith('/transcript')).flatMap(r=>r.data.entries);
  assert.ok(saved.some(row=>row.role==='assistant'&&row.content==='The sailor found'&&row.interrupted===true));
  assert.equal(s.socket.onmessage,null);assert.equal(f.controller.active,false);
});

function protocolFixture(){
  class Socket{
    constructor(){this.listeners={};this.sent=[];}
    addEventListener(name,fn){this.listeners[name]=fn;}
    send(value){if(this.rejectSend)throw new Error('closed');this.sent.push(value);}
    emit(name,data){this.listeners[name]?.(data);}
  }
  const window={WebSocket:Socket};
  vm.runInNewContext('('+require('./voice_proof_diagnostics.cjs').toString()+')()',{window,Date,TextDecoder});
  const socket=new window.WebSocket('wss://secret.example?access_token=secret-token');
  const receive=value=>socket.emit('message',{data:JSON.stringify(value)});
  return{window,socket,receive,snapshot:()=>window.voiceEvents.snapshot()};
}
test('voice proof retains event order and pending tools without private payloads',()=>{
  const f=protocolFixture();f.socket.emit('open',{});
  f.receive({toolCall:{functionCalls:[{id:'private-tool-id',name:'secret-tool',args:{message:'private context'}}]}});
  f.receive({serverContent:{modelTurn:{parts:[{inlineData:{mimeType:'audio/pcm',data:'private-audio'}}]}}});
  f.socket.emit('close',{code:1011,wasClean:true,reason:'Internal error with secret-token and private account'});
  const proof=f.snapshot();assert.equal(proof.pending,1);assert.equal(proof.counts.outputAudio,1);
  assert.equal(proof.events.at(-1).classification,'internal');
  assert.deepEqual(Array.from(proof.events,e=>e.kind),['open','tool_call','close']);
  assert.equal(proof.events.at(-1).counts.toolResponses,0);
  assert.doesNotMatch(JSON.stringify(proof),/private|secret|wss|access_token/);
});
test('voice proof records successful tool responses and cancellations but not failed sends',()=>{
  const f=protocolFixture();f.receive({toolCall:{functionCalls:[{id:'one'},{id:'two'}]}});
  f.socket.rejectSend=true;
  assert.throws(()=>f.socket.send(JSON.stringify({toolResponse:{functionResponses:[{id:'one'}]}})),/closed/);
  assert.equal(f.snapshot().counts.toolResponses,0);assert.equal(f.snapshot().pending,2);
  f.socket.rejectSend=false;f.socket.send(JSON.stringify({toolResponse:{functionResponses:[{id:'one',response:{result:'secret answer'}}]}}));
  f.receive({toolCallCancellation:{ids:['two']}});
  f.receive({serverContent:{generationComplete:true,turnComplete:true}});
  assert.equal(f.snapshot().pending,0);assert.equal(f.snapshot().counts.toolResponses,1);
  assert.equal(f.snapshot().counts.cancellations,1);assert.equal(f.snapshot().counts.turns,1);
  assert.doesNotMatch(JSON.stringify(f.snapshot()),/secret answer/);
});
test('voice diagnostics bound history and classify close reasons without copying them',()=>{
  for(const [reason,category]of [['Your prepayment credits are depleted. secret','prepaid_depleted'],
      ['RESOURCE_EXHAUSTED secret','resource_exhausted'],['DEADLINE_EXCEEDED secret','deadline_exceeded'],
      ['UNAVAILABLE secret','unavailable'],['INVALID_ARGUMENT secret','invalid_argument'],['secret','unclassified'],['','empty']]){
    const f=protocolFixture();for(let n=0;n<140;n++)f.receive({serverContent:{turnComplete:true}});
    f.socket.emit('close',{code:1011,wasClean:true,reason});const proof=f.snapshot();
    assert.equal(proof.events.length,128);assert.equal(proof.dropped,13);assert.equal(proof.counts.turns,140);
    assert.equal(proof.events.at(-1).classification,category);assert.doesNotMatch(JSON.stringify(proof),/secret/);
  }
});
test('failure diagnostics cannot prevent cleanup on older sessions or an observer error',()=>{
  const f=protocolFixture(),observed=[];let cleaned=0;
  const prototype={fail(s,message){assert.equal(s,this.session);assert.equal(message,'safe');cleaned++;}};
  f.window.voiceEvents.wrapFailure(prototype,s=>observed.push(s));
  const oldSession={sources:new Set(),nextAudio:0,audio:{currentTime:0}},controller=Object.create(prototype);
  controller.session=oldSession;controller.fail(oldSession,'safe');
  assert.equal(cleaned,1);assert.equal(observed[0].pendingTools,null);
  controller.session={get pendingTools(){throw new Error('untrusted private error');}};
  controller.fail(controller.session,'safe');assert.equal(cleaned,2);
  f.window.voiceEvents.wrapFailure(prototype,()=>{throw new Error('observer error');});
  controller.session=oldSession;controller.fail(oldSession,'safe');assert.equal(cleaned,3);
  assert.doesNotMatch(JSON.stringify(observed),/untrusted|private/);
});
test('private text results and confirmation tokens never reach voice provider',async t=>{
  const f=fixture({api:async(route)=>{
    if(route.endsWith('/start'))return {call_id:'fixture',url:'wss://example',token:'token',expires_at:Date.now()/1000+600};
    if(route.endsWith('/tool'))return {request_id:'r',conversation:{messages:[{role:'assistant',request_id:'r',status:'done',texting:true,content:'Private thread wbtxt-secret'}]}};
    return {ok:true,settled:true};
  }});
  t.after(()=>f.controller.stop());await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{serverContent:{inputTranscription:{text:'texts'}}});s.inputTurn.lastInputAt=0;
  await f.controller.tool(s,{id:'private',name:'ask_bob'});
  const sent=JSON.stringify(s.socket.sent);
  assert.ok(!sent.includes('Private thread')&&!sent.includes('wbtxt-secret'));
  assert.match(sent,/read it on screen/);
});
test('an interrupted turn cannot swallow the next spoken utterance',async()=>{
  const f=fixture();await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{serverContent:{inputTranscription:{text:'Tell me a story'},outputTranscription:{text:'Once upon a time'}}});
  f.controller.event(s,{serverContent:{interrupted:true}});
  f.controller.event(s,{serverContent:{inputTranscription:{text:'Stop please'}}});
  f.controller.event(s,{serverContent:{turnComplete:true}});
  assert.equal(s.turns.length,2);assert.equal(s.turns[0].user,'Tell me a story');
  assert.equal(s.turns[1].user,'Stop please');assert.equal(s.turns[1].finished,false);await f.controller.stop();
});
test('private memory inspection results never enter a voice tool response',async t=>{
  const f=fixture({api:async(route)=>{
    if(route.endsWith('/start'))return {call_id:'fixture',url:'wss://example',token:'token',expires_at:Date.now()/1000+600};
    if(route.endsWith('/tool'))return {request_id:'r',conversation:{messages:[{role:'assistant',request_id:'r',status:'done',
      private_memory:true,content:'Private saved-note fixture copper-puffin-739'}]}};
    return {ok:true,settled:true};
  }});
  t.after(()=>f.controller.stop());await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{serverContent:{inputTranscription:{text:'show my saved memories'}}});s.inputTurn.lastInputAt=0;
  await f.controller.tool(s,{id:'memory',name:'ask_bob'});
  const sent=JSON.stringify(s.socket.sent);
  assert.ok(!sent.includes('copper-puffin-739'));
  assert.match(sent,/saved memory view is ready in chat/);
});
test('suspended Safari output keeps Resume audio visible',async()=>{
  const f=fixture();await f.controller.start('chat');const s=f.controller.session;
  s.audio.state='suspended';f.controller.play(s,{data:btoa('\0'.repeat(4800)),mimeType:'audio/pcm;rate=24000'});
  assert.equal(f.states.at(-1).phase,'paused');await f.controller.resume();assert.equal(s.audio.state,'running');await f.controller.stop();
});
test('Safari suspension keeps Resume visible and blocks speech until an explicit resume',async t=>{
  const f=fixture();t.after(()=>f.controller.stop());await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{setupComplete:{}});
  s.audio.state='suspended';s.audio.onstatechange();
  const sent=s.socket.sent.length;
  s.capture.port.onmessage({data:new ArrayBuffer(3200)});
  assert.equal(s.socket.sent.length,sent,'speaking while suspended must not send packets');
  for(const event of [{setupComplete:{}},{serverContent:{interrupted:true}},{serverContent:{turnComplete:true}}]) {
    f.controller.event(s,event);
    assert.equal(f.states.at(-1).phase,'paused','incoming events must preserve the resume action');
  }
  await f.controller.retrySave();assert.equal(f.states.at(-1).phase,'paused');
  assert.equal(s.audio.state,'suspended','no automatic resume');
  await f.controller.resume();
  assert.equal(s.audio.state,'running');
  s.capture.port.onmessage({data:new ArrayBuffer(3200)});
  assert.equal(s.socket.sent.length,sent+1);
  await f.controller.stop();
});
test('a late Safari resume cannot overwrite the ended-call state',async t=>{
  const f=fixture();t.after(()=>f.controller.stop());await f.controller.start('chat');const s=f.controller.session;
  const resume=deferred();s.audio.resume=()=>resume.promise;
  const resuming=f.controller.resume();await f.controller.stop();resume.resolve();await resuming;
  assert.equal(f.controller.active,false);assert.equal(f.states.at(-1).phase,'ended');
});
test('token expiry mid-call releases audio and saves interrupted speech without restarting',async()=>{
  const timers=new Map();let next=0;
  const f=fixture({clock:{
    setTimeout:(callback,ms)=>{const id=++next;timers.set(id,{callback,ms});return id;},
    clearTimeout:id=>timers.delete(id),
    setInterval:(callback,ms)=>{const id=++next;timers.set(id,{callback,ms});return id;},
    clearInterval:id=>timers.delete(id),
  }});
  await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{setupComplete:{}});
  f.controller.event(s,{serverContent:{inputTranscription:{text:'Please keep this'},outputTranscription:{text:'Here is my reply'}}});
  f.controller.play(s,{data:btoa('\0'.repeat(4800)),mimeType:'audio/pcm;rate=24000'});
  const sources=[...s.sources];
  assert.ok(timers.get(s.expiry).ms>599000 && timers.get(s.expiry).ms<=600000);
  timers.get(s.expiry).callback();await pause();
  assert.equal(f.controller.active,false);assert.equal(f.tracks[0].stopped,true);
  assert.equal(s.audio.state,'closed');assert.equal(s.socket.closed,true);
  assert.ok(sources.every(source=>source.stopped));assert.equal(timers.size,0);
  assert.equal(f.requests.filter(r=>r.route.endsWith('/start')).length,1);
  assert.equal(f.requests.filter(r=>r.route.endsWith('/end')).length,1);
  const saved=f.requests.filter(r=>r.route.endsWith('/transcript')).flatMap(r=>r.data.entries);
  assert.ok(saved.some(row=>row.role==='assistant' && row.interrupted));
  assert.match(f.states.at(-1).text,/10-minute call has ended/);
});
test('barge-in during a dispatched tool preserves interrupted transcript on save retry',async t=>{
  const dispatched=deferred();let savesFail=true;
  const f=fixture({api:async(route,data)=>{
    if(route.endsWith('/start'))return {call_id:'fixture',url:'wss://example',token:'token',expires_at:Date.now()/1000+600};
    if(route.endsWith('/transcript') && savesFail && data.entries.some(row=>row.interrupted))throw new Error('offline');
    if(route.endsWith('/tool'))return dispatched.promise;
    return {ok:true,settled:true};
  }});
  t.after(()=>f.controller.stop());
  await f.controller.start('chat');const s=f.controller.session;
  f.controller.event(s,{serverContent:{inputTranscription:{text:'Check my request'},outputTranscription:{text:'I am checking'}}});
  s.inputTurn.lastInputAt=0;
  f.controller.play(s,{data:btoa('\0'.repeat(4800)),mimeType:'audio/pcm;rate=24000'});
  const sources=[...s.sources];
  f.controller.event(s,{toolCall:{functionCalls:[{id:'slow',name:'ask_bob'}]}});
  await pause();assert.equal(f.requests.filter(r=>r.route.endsWith('/tool')).length,1);
  f.controller.event(s,{toolCallCancellation:{ids:['slow']},serverContent:{interrupted:true}});
  assert.ok(sources.every(source=>source.stopped));
  await f.controller.save(s);assert.equal(f.controller.pending.length,1);
  dispatched.resolve({request_id:'r',conversation:{messages:[{role:'assistant',request_id:'r',status:'done',content:'Saved receipt'}]}});
  await s.tools.get('slow');
  assert.equal(s.socket.sent.filter(m=>m.toolResponse).length,0,'cancelled result cannot speak later');
  f.controller.event(s,{toolCall:{functionCalls:[{id:'slow',name:'ask_bob'}]}});
  assert.equal(f.requests.filter(r=>r.route.endsWith('/tool')).length,1,'replayed tool cannot dispatch twice');
  savesFail=false;await f.controller.retrySave();assert.equal(f.controller.pending.length,0);
  const saved=f.requests.filter(r=>r.route.endsWith('/transcript')).at(-1).data.entries;
  assert.ok(saved.some(row=>row.role==='assistant' && row.interrupted && row.version>=2));
  f.controller.event(s,{serverContent:{inputTranscription:{text:'Try the next question'}}});
  s.inputTurn.lastInputAt=0;
  await f.controller.tool(s,{id:'next',name:'ask_bob'});
  const requests=f.requests.filter(r=>r.route.endsWith('/tool'));
  assert.equal(requests.length,2);assert.notEqual(requests[0].data.turn_id,requests[1].data.turn_id);
  await f.controller.stop();
});
test('hangup releases the server lease even while transcript saving is blocked',async()=>{
  const pending=deferred();const f=fixture({api:async(route)=>{
    if(route.endsWith('/start'))return {call_id:'fixture',url:'wss://example',token:'token',expires_at:Date.now()/1000+600};
    if(route.endsWith('/transcript'))return pending.promise;
    return {ok:true,settled:true};
  }});
  await f.controller.start('chat');f.controller.event(f.controller.session,{serverContent:{inputTranscription:{text:'Keep this'}}});
  const stopping=f.controller.stop();await pause();
  assert.ok(f.requests.some(r=>r.route.endsWith('/end')));assert.equal(f.tracks[0].stopped,true);
  pending.resolve({ok:true});await stopping;
});
for(const rate of [16000,44100,48000])test(`worklet resamples ${rate} Hz to exactly 1600 PCM samples per 100 ms`,()=>{
  let Processor;const packets=[];
  const context={sampleRate:rate,AudioWorkletProcessor:class{constructor(){this.port={postMessage:data=>packets.push(data)};}},
    registerProcessor:(_,processor)=>{Processor=processor;}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'static/voice-capture.js'),'utf8'),context);
  const p=new Processor();p.process([[new Float32Array(rate/10).fill(.5)]]);
  assert.equal(packets.length,1);assert.equal(packets[0].byteLength,3200);
  const pcm=new DataView(packets[0]);
  for (const offset of [0,3198]) assert.ok(Math.abs(pcm.getInt16(offset,true)-16384)<=1, 'PCM rounding within one quantization step');
});
