/* Proof-only, bounded protocol metadata. Never retain provider text, arguments,
   tool IDs, credentials, socket URLs, or audio in this diagnostic record. */
function installVoiceDiagnostics() {
  const NativeSocket = window.WebSocket;
  const started = Date.now(), events = [], pending = new Set();
  const counts = {received:0,sent:0,inputAudio:0,outputAudio:0,toolCalls:0,
    toolResponses:0,cancellations:0,turns:0,generations:0,interruptions:0};
  let sequence = 0, dropped = 0, overflow = false;
  function classification(reason) {
    const text = typeof reason === 'string' ? reason.slice(0,4096) : '';
    if (/prepayment credits are depleted/i.test(text)) return 'prepaid_depleted';
    if (/resource[_ ]exhausted/i.test(text)) return 'resource_exhausted';
    if (/deadline[_ ]exceeded/i.test(text)) return 'deadline_exceeded';
    if (/unavailable/i.test(text)) return 'unavailable';
    if (/internal(?:[_ ](?:error|server error))?/i.test(text)) return 'internal';
    if (/invalid[_ ]argument/i.test(text)) return 'invalid_argument';
    return text ? 'unclassified' : 'empty';
  }
  function record(kind, fields = {}) {
    events.push({seq:++sequence,elapsed_ms:Date.now()-started,kind,...fields,
      counts:{...counts},pending:pending.size});
    if (events.length > 128) { events.shift(); dropped++; }
  }
  function receive(value) {
    counts.received++;
    const c = value.serverContent || {};
    if (value.setupComplete) record('setup_complete');
    if (value.toolCall) {
      for (const tool of (value.toolCall.functionCalls || []).slice(0,64)) {
        counts.toolCalls++;
        if (typeof tool.id === 'string' && tool.id.length <= 512 && pending.size < 64) pending.add(tool.id);
        else overflow = true;
      }
      record('tool_call');
    }
    if (value.toolCallCancellation) {
      for (const id of (value.toolCallCancellation.ids || []).slice(0,64)) {
        counts.cancellations++; pending.delete(id);
      }
      record('tool_cancelled');
    }
    counts.outputAudio += (c.modelTurn?.parts || []).filter(p=>p.inlineData?.mimeType?.startsWith('audio/pcm')).length;
    if (c.interrupted) { counts.interruptions++; record('interrupted'); }
    if (c.generationComplete) { counts.generations++; record('generation_complete'); }
    if (c.turnComplete) { counts.turns++; record('turn_complete'); }
    if (value.goAway) record('go_away');
    if (value.error) record('server_error',{classification:classification(value.error.message)});
  }
  window.voiceEvents = {snapshot:()=>({counts:{...counts},pending:pending.size,
    pending_overflow:overflow,dropped,events:events.map(e=>({...e,counts:{...e.counts}}))})};
  window.voiceEvents.wrapFailure = (prototype, observe) => {
    const original=prototype.fail;
    prototype.fail=function(s,...args){
      try {
        if(this.session===s)observe({pendingTools:s.pendingTools?.size??null,queuedSources:s.sources?.size??null,
          queuedSeconds:Math.max(0,(s.nextAudio||0)-(s.audio?.currentTime||0)),ready:s.ready===true,
          inputFinished:s.inputTurn?.finished===true,outputFinished:s.outputTurn?.finished===true,
          protocol:window.voiceEvents.snapshot()});
      } catch (_) { /* Diagnostics must never prevent the original cleanup. */ }
      return original.call(this,s,...args);
    };
  };
  window.WebSocket = class extends NativeSocket {
    constructor(...args) {
      super(...args);
      this.addEventListener('open',()=>record('open'));
      this.addEventListener('error',()=>record('socket_error'));
      this.addEventListener('close',event=>record('close',{
        code:Number.isInteger(event.code)?event.code:null,clean:event.wasClean===true,
        classification:classification(event.reason),reason_length:typeof event.reason==='string'?event.reason.length:0}));
      this.addEventListener('message',event=>{
        try { receive(JSON.parse(typeof event.data==='string'?event.data:new TextDecoder().decode(event.data))); }
        catch (_) { record('unparsed_message'); }
      });
    }
    send(raw) {
      // Only count successfully accepted sends. Diagnostics never change failure semantics.
      const result = super.send(raw);
      try {
        const value = JSON.parse(raw); counts.sent++;
        if (value.realtimeInput?.audio) counts.inputAudio++;
        if (value.toolResponse) {
          for (const response of (value.toolResponse.functionResponses || []).slice(0,64)) {
            counts.toolResponses++; pending.delete(response.id);
          }
          record('tool_response');
        }
      } catch (_) { record('unparsed_send'); }
      return result;
    }
  };
}
module.exports = installVoiceDiagnostics;
