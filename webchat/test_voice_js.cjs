const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, 'static/voice.js'), 'utf8');
const pause = () => new Promise(resolve => setImmediate(resolve));
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
    return {ok:true};
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
test('hanging up during microphone permission stops a late stream',async()=>{
  const mic=deferred(),f=fixture({getUserMedia:()=>mic.promise});
  const starting=f.controller.start('chat');await f.controller.stop();mic.resolve(f.stream);await starting;
  assert.equal(f.tracks[0].stopped,true);assert.equal(f.sockets.length,0);
});
test('hanging up while token request is pending ends that late session',async()=>{
  const token=deferred();const f=fixture({api:async(route)=>route.endsWith('/start')?token.promise:{ok:true}});
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
    return {ok:true};
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
    return {ok:true};
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
test('private text results and confirmation tokens never reach voice provider',async t=>{
  const f=fixture({api:async(route)=>{
    if(route.endsWith('/start'))return {call_id:'fixture',url:'wss://example',token:'token',expires_at:Date.now()/1000+600};
    if(route.endsWith('/tool'))return {request_id:'r',conversation:{messages:[{role:'assistant',request_id:'r',status:'done',texting:true,content:'Private thread wbtxt-secret'}]}};
    return {ok:true};
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
    return {ok:true};
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
    return {ok:true};
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
