/* AudioWorklet: mono, little-endian PCM16 at 16 kHz, in 100 ms packets.
   Integrate samples across rate boundaries (including Safari's 44.1/48 kHz).
   The output is silence: the caller must never hear their own microphone. */
class BobVoiceCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.remaining = this.ratio;
    this.sum = 0;
    this.packet = new ArrayBuffer(3200);
    this.view = new DataView(this.packet);
    this.offset = 0;
  }
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    for (const sample of channel) {
      let available = 1;
      while (available > 1e-8) {
        const portion = Math.min(available, this.remaining);
        this.sum += sample * portion;
        available -= portion;
        this.remaining -= portion;
        if (this.remaining < 1e-8) {
          const value = Math.max(-1, Math.min(1, this.sum / this.ratio));
          this.view.setInt16(this.offset, Math.round(value * (value < 0 ? 32768 : 32767)), true);
          this.offset += 2;
          this.remaining = this.ratio;
          this.sum = 0;
          if (this.offset === this.packet.byteLength) {
            this.port.postMessage(this.packet, [this.packet]);
            this.packet = new ArrayBuffer(3200);
            this.view = new DataView(this.packet);
            this.offset = 0;
          }
        }
      }
    }
    return true;
  }
}
registerProcessor("bob-voice-capture", BobVoiceCapture);
