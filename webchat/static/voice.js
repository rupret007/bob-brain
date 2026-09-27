"use strict";
/* Full-duplex Gemini Live audio. Dictation/read-aloud remain separate features.
   This controller owns every resource, including late microphone promises. */
class BobVoice {
  constructor({ api, onState, onTranscript, onSaved }) {
    Object.assign(this, { api, onState, onTranscript, onSaved });
    this.session = null;
    this.pending = [];
    this.flushing = null;
  }
  get active() { return !!this.session; }
  state(text, phase = "listening") { this.onState(text, phase); }
  async start(conversationId) {
    if (this.active) return this.stop();
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      this.state("Open Bob’s HTTPS address to allow microphone access.", "error"); return;
    }
    if (!window.AudioContext || !window.AudioWorkletNode || !window.WebSocket) {
      this.state("Live calls need a browser with streaming audio support. Try current Safari or Chrome.", "error"); return;
    }
    const s = { conversationId, entries: new Map(), turns: [], sources: new Set(), nextAudio: 0,
      tools: new Map(), cancelledTools: new Set(), closed: false, ready: false };
    this.session = s;
    this.state("Connecting… allow the microphone when asked.", "connecting");
    try {
      // Both calls start in the tap handler, before the first await. Safari needs
      // user activation to unlock output, even when microphone access is granted.
      s.audio = new AudioContext();
      const unlocked = s.audio.resume();
      const microphone = navigator.mediaDevices.getUserMedia({ audio: {
        echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1,
      }});
      s.connectTimeout = setTimeout(() => this.fail(s, "The call took too long to connect. Tap the waveform to retry."), 30000);
      s.stream = await microphone;
      if (this.session !== s) { s.stream.getTracks().forEach(t => t.stop()); return; }
      await unlocked;
      for (const track of s.stream.getTracks()) {
        track.addEventListener("ended", () => this.fail(s, "Microphone disconnected. Tap the waveform to call again."));
      }
      s.audio.onstatechange = () => {
        if (this.session === s && !["running", "closed"].includes(s.audio.state)) this.state("Tap Resume audio to continue the call.", "paused");
      };
      await s.audio.audioWorklet.addModule("/voice-capture.js");
      if (this.session !== s) return;
      const info = await this.api("/api/voice/start", { conversation_id: conversationId });
      s.callId = info.call_id;
      if (this.session !== s) { await this.api("/api/voice/end", { call_id: s.callId }); return; }
      s.socket = new WebSocket(info.url + "?access_token=" + encodeURIComponent(info.token));
      s.socket.binaryType = "arraybuffer";
      s.socket.onopen = () => {
        if (this.session === s) this.send(s, { setup: { model: info.model } });
      };
      s.socket.onmessage = event => {
        if (this.session !== s) return;
        try {
          const raw = typeof event.data === "string" ? event.data : new TextDecoder().decode(event.data);
          this.event(s, JSON.parse(raw));
        } catch (_) { this.fail(s, "The voice connection failed. Your saved transcript is in chat."); }
      };
      s.socket.onerror = () => this.fail(s, "The voice connection failed. Check your connection and try again.");
      s.socket.onclose = () => this.fail(s, "Call disconnected. Tap the waveform to call again.");
      s.expiry = setTimeout(() => this.fail(s, "This 10-minute call has ended. Tap the waveform to continue."), Math.max(0, info.expires_at * 1000 - Date.now()));
      s.flushTimer = setInterval(() => this.save(s), 700);
      s.pulseTimer = setInterval(async () => {
        try { await this.api("/api/voice/pulse", { call_id: s.callId }); s.pulseFailures = 0; }
        catch (_) {
          s.pulseFailures = (s.pulseFailures || 0) + 1;
          if (s.pulseFailures >= 3) this.fail(s, "Connection to Bob was lost. Tap the waveform to try again.");
        }
      }, 10000);
      s.input = s.audio.createMediaStreamSource(s.stream);
      s.capture = new AudioWorkletNode(s.audio, "bob-voice-capture");
      s.silent = s.audio.createGain(); s.silent.gain.value = 0;
      s.capture.port.onmessage = event => {
        if (this.session !== s || !s.ready || s.audio.state !== "running") return;
        if (s.socket.bufferedAmount > 128000) {
          this.fail(s, "The connection is too slow for live audio. Please call again."); return;
        }
        const bytes = new Uint8Array(event.data);
        let binary = "";
        for (const byte of bytes) binary += String.fromCharCode(byte);
        this.send(s, { realtimeInput: { audio: { data: btoa(binary), mimeType: "audio/pcm;rate=16000" } } });
      };
      s.input.connect(s.capture).connect(s.silent).connect(s.audio.destination);
    } catch (error) {
      if (this.session !== s) return;
      const message = error.name === "NotAllowedError"
        ? "Microphone blocked. Allow microphone access in Safari’s website settings, then try again."
        : error.name === "NotFoundError" ? "No microphone found. Connect one and try again."
        : error.name === "NotReadableError" ? "The microphone is in use. Close the other recording and try again."
        : error.message || "Could not start the call. Please try again.";
      this.fail(s, message);
    }
  }
  send(s, message) {
    if (this.session === s && s.socket?.readyState === WebSocket.OPEN) s.socket.send(JSON.stringify(message));
  }
  newTurn(s) {
    const turn = { id: crypto.randomUUID(), order: s.turns.length, user: "", assistant: "", finished: false };
    s.turns.push(turn); s.inputTurn = turn;
    return turn;
  }
  entry(s, turn, role) {
    const row = { turn_id: turn.id, role, order: turn.order, content: turn[role], interrupted: !!turn.interrupted,
      version: (s.entries.get(turn.id + role)?.version || 0) + 1 };
    s.entries.set(turn.id + role, row);
    this.onTranscript([...s.entries.values()].sort((a, b) => a.order - b.order || (a.role === "user" ? -1 : 1)));
  }
  event(s, event) {
    if (event.setupComplete) {
      s.ready = true; clearTimeout(s.connectTimeout);
      this.state("Listening… speak naturally. You can interrupt Bob anytime.");
    }
    if (event.error) { this.fail(s, "The voice service could not continue this call. Please try again."); return; }
    if (event.goAway) { this.fail(s, "The voice session has ended. Tap the waveform to continue."); return; }
    for (const id of event.toolCallCancellation?.ids || []) s.cancelledTools.add(id);
    const content = event.serverContent || {};
    if (content.interrupted) {
      this.clearAudio(s);
      if (s.outputTurn) {
        s.outputTurn.interrupted = true;
        s.outputTurn.finished = true;
        this.entry(s, s.outputTurn, "assistant");
        s.interruptedTurn = s.outputTurn;
        s.outputTurn = null;
      }
      this.state("Listening… Bob stopped speaking.");
    }
    if (content.inputTranscription?.text) {
      let turn = s.inputTurn;
      if (!turn || turn.finished) turn = this.newTurn(s);
      turn.user += content.inputTranscription.text;
      turn.lastInputAt = Date.now();
      this.entry(s, turn, "user");
    }
    if (content.outputTranscription?.text) {
      const turn = s.outputTurn || s.inputTurn || this.newTurn(s);
      s.outputTurn = turn;
      turn.assistant += content.outputTranscription.text;
      this.entry(s, turn, "assistant");
    }
    for (const part of content.modelTurn?.parts || []) {
      if (part.inlineData?.mimeType?.startsWith("audio/pcm")) {
        s.outputTurn ||= s.inputTurn || this.newTurn(s);
        this.play(s, part.inlineData);
      }
    }
    if (content.turnComplete) {
      const turn = s.interruptedTurn || s.outputTurn || s.inputTurn;
      if (turn) turn.finished = true;
      if (s.outputTurn === turn) s.outputTurn = null;
      s.interruptedTurn = null;
      this.save(s);
      if (!s.sources.size) this.state("Listening… speak whenever you’re ready.");
    }
    for (const tool of event.toolCall?.functionCalls || []) {
      if (!s.tools.has(tool.id)) {
        const work = this.tool(s, tool);
        s.tools.set(tool.id, work);
      }
    }
  }
  play(s, data) {
    const raw = atob(data.data), bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const rate = Number(/rate=(\d+)/.exec(data.mimeType)?.[1] || 24000);
    if (rate < 8000 || rate > 96000 || !bytes.length || bytes.length % 2) throw new Error("Invalid audio");
    const buffer = s.audio.createBuffer(1, bytes.length / 2, rate), values = buffer.getChannelData(0);
    const pcm = new DataView(bytes.buffer);
    for (let i = 0; i < values.length; i++) values[i] = pcm.getInt16(i * 2, true) / 32768;
    const source = s.audio.createBufferSource(); source.buffer = buffer; source.connect(s.audio.destination);
    s.playingTurn = s.outputTurn;
    const when = Math.max(s.audio.currentTime + .02, s.nextAudio);
    if (when - s.audio.currentTime > 30) throw new Error("Audio backlog");
    s.nextAudio = when + buffer.duration; s.sources.add(source);
    source.onended = () => {
      s.sources.delete(source); source.disconnect();
      if (this.session === s && !s.sources.size && s.audio.state === "running") this.state("Listening… speak whenever you’re ready.");
    };
    source.start(when);
    if (s.audio.state === "running") this.state("Bob is speaking · interrupt anytime", "speaking");
    else this.state("Tap Resume audio to continue the call.", "paused");
  }
  clearAudio(s) {
    for (const source of s.sources) { source.onended = null; try { source.stop(); source.disconnect(); } catch (_) {} }
    s.sources.clear(); s.nextAudio = 0;
  }
  async tool(s, tool) {
    try {
      if (tool.name !== "ask_bob") throw new Error("This tool is not available.");
      const turn = s.inputTurn || this.newTurn(s);
      // Input transcription is independent of tool events; allow it to catch up.
      for (let n = 0; n < 30 && (!turn.user.trim() || Date.now() - turn.lastInputAt < 350); n++) await new Promise(r => setTimeout(r, 100));
      if (this.session !== s || s.cancelledTools.has(tool.id)) return;
      if (!turn?.user.trim()) throw new Error("I couldn’t transcribe that request. Please repeat it.");
      this.state("Bob is checking… you can keep speaking.", "thinking");
      await this.save(s, true);
      if (this.session !== s || s.cancelledTools.has(tool.id)) return;
      const result = await this.api("/api/voice/tool", { call_id: s.callId, turn_id: turn.id });
      let conversation = result.conversation, answer;
      const deadline = Date.now() + 180000;
      while (this.session === s && !s.cancelledTools.has(tool.id)) {
        answer = conversation.messages.find(m => m.role === "assistant" && m.request_id === result.request_id);
        if (answer && !["running", "queued"].includes(answer.status)) break;
        if (Date.now() > deadline) throw new Error("That reply is still in progress. Check this chat for the result.");
        await new Promise(r => setTimeout(r, 350));
        conversation = await this.api("/api/conversations/" + s.conversationId);
      }
      if (this.session !== s || s.cancelledTools.has(tool.id)) return;
      this.send(s, { toolResponse: { functionResponses: [{ id: tool.id, name: tool.name,
        response: { result: answer?.content || "No result was returned.", status: answer?.status || "error" } }] } });
    } catch (error) {
      if (this.session === s && !s.cancelledTools.has(tool.id)) this.send(s, {
        toolResponse: { functionResponses: [{ id: tool.id, name: tool.name, response: { error: error.message } }] },
      });
    }
  }
  async save(s, required = false) {
    if (!s.callId || !s.entries.size) return;
    // Queue snapshots; later snapshots of the same call supersede earlier ones.
    const entries = [...s.entries.values()].filter(row => row.content.trim());
    this.pending = this.pending.filter(p => p.call_id !== s.callId);
    this.pending.push({ call_id: s.callId, entries });
    try {
      await this.flush();
    } catch (error) {
      this.state("Transcript hasn’t saved yet. Keep this page open and tap Retry save.", "unsaved");
      if (required) throw error;
    }
  }
  flush() {
    if (!this.flushing) this.flushing = this.flushQueue().finally(() => { this.flushing = null; });
    return this.flushing;
  }
  async flushQueue() {
    while (this.pending.length) {
      const payload = this.pending[0];
      // Bounded requests keep pagehide keepalive below the browser's 64 KiB limit.
      let batch = [];
      const send = entries => this.api("/api/voice/transcript", { call_id: payload.call_id, entries });
      for (const entry of payload.entries) {
        if (batch.length >= 40 || (batch.length && new TextEncoder().encode(JSON.stringify([...batch, entry])).length > 48000)) {
          await send(batch); batch = [];
        }
        batch.push(entry);
      }
      if (batch.length) await send(batch);
      if (this.pending[0] === payload) this.pending.shift();
    }
    this.onSaved();
  }
  async retrySave() {
    try { await this.flush(); this.state(this.active ? "Listening… transcript saved." : "Call ended · transcript saved to chat.", this.active ? "listening" : "ended"); }
    catch (_) { this.state("Transcript hasn’t saved yet. Keep this page open and tap Retry save.", "unsaved"); }
  }
  async resume() {
    if (!this.session) return;
    try { await this.session.audio.resume(); this.state("Listening… speak naturally."); }
    catch (_) { this.state("Could not resume audio. End this call and try again.", "error"); }
  }
  fail(s, message) {
    if (this.session !== s) return;
    this.stop(message);
  }
  async stop(message) {
    const s = this.session;
    if (!s) return;
    this.session = null; s.closed = true;
    clearTimeout(s.connectTimeout); clearTimeout(s.expiry); clearInterval(s.flushTimer); clearInterval(s.pulseTimer);
    s.stream?.getTracks().forEach(track => track.stop());
    if (s.socket) { s.socket.onclose = s.socket.onerror = s.socket.onmessage = null; s.socket.close(); }
    if (s.capture) { s.capture.port.onmessage = null; s.capture.disconnect(); }
    s.input?.disconnect(); s.silent?.disconnect();
    if (s.sources.size && s.playingTurn) { s.playingTurn.interrupted = true; this.entry(s, s.playingTurn, "assistant"); }
    this.clearAudio(s);
    if (s.audio) { s.audio.onstatechange = null; s.audio.close().catch(() => {}); }
    if (s.outputTurn) { s.outputTurn.interrupted = true; this.entry(s, s.outputTurn, "assistant"); }
    this.state(message || "Call ended · saving transcript…", message ? "error" : "ended");
    // Release the slot synchronously on pagehide, before awaiting any saves.
    // Both requests use keepalive, and the server accepts final writes after end.
    const ending = s.callId ? this.api("/api/voice/end", { call_id: s.callId }).catch(() => {}) : Promise.resolve();
    await this.save(s);
    await ending;
    if (!this.active && !this.pending.length) this.state(message || "Call ended · transcript saved to chat.", message ? "error" : "ended");
  }
}
window.BobVoice = BobVoice;
