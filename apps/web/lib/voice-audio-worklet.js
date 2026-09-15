/* global AudioWorkletProcessor, registerProcessor, sampleRate */
// One continuously running processor captures and plays audio concurrently at 24 kHz.
class LiveVoiceAudio extends AudioWorkletProcessor {
  constructor() {
    super();
    this.capture = new Int16Array(480);
    this.captureOffset = 0;
    // WebSocket delivery may batch more than one second of generated speech.
    // Keep a bounded five-second jitter buffer while playback starts immediately.
    this.output = new Float32Array(24000 * 5);
    this.readOffset = 0;
    this.writeOffset = 0;
    this.queued = 0;
    this.playing = false;
    this.playbackTail = 0;
    this.running = false;
    this.levelSamples = 0;
    this.levelEnergy = 0;
    this.port.onmessage = ({ data }) => {
      if (data.type === 'start') this.running = true;
      if (data.type === 'stop') {
        this.running = false;
        this.queued = 0;
      }
      if (data.type === 'audio' && this.running) {
        const samples = new Int16Array(data.buffer);
        if (samples.length + this.queued > this.output.length) {
          this.port.postMessage({ type: 'overflow' });
          this.running = false;
          this.queued = 0;
          return;
        }
        for (const sample of samples) {
          this.output[this.writeOffset] = sample / 32768;
          this.writeOffset = (this.writeOffset + 1) % this.output.length;
        }
        this.queued += samples.length;
      }
    };
    if (sampleRate !== 24000) this.port.postMessage({ type: 'unsupported-rate' });
  }
  process(inputs, outputs) {
    const input = inputs[0]?.[0];
    const output = outputs[0]?.[0];
    if (!output) return true;
    let audible = false;
    for (let i = 0; i < output.length; i++) {
      output[i] = 0;
      if (!this.running) continue;
      const value = Math.max(-1, Math.min(1, input?.[i] || 0));
      this.capture[this.captureOffset++] = value < 0 ? value * 32768 : value * 32767;
      if (this.captureOffset === this.capture.length) {
        const buffer = this.capture.buffer;
        this.port.postMessage({ type: 'audio', buffer }, [buffer]);
        this.capture = new Int16Array(480);
        this.captureOffset = 0;
      }
      if (this.queued) {
        output[i] = this.output[this.readOffset];
        if (Math.abs(output[i]) > 0.0001) audible = true;
        this.readOffset = (this.readOffset + 1) % this.output.length;
        this.queued--;
      }
    }
    for (let i = 0; i < output.length; i++) {
      const capture = this.running ? input?.[i] || 0 : 0;
      this.levelEnergy += Math.max(capture * capture, output[i] * output[i]);
      this.levelSamples++;
      if (this.levelSamples >= 1200) {
        this.port.postMessage({ type: 'level', value: Math.min(1, Math.sqrt(this.levelEnergy / this.levelSamples) * 5) });
        this.levelEnergy = 0;
        this.levelSamples = 0;
      }
    }
    this.playbackTail = !this.running ? 0 : audible ? 7200 : Math.max(0, this.playbackTail - output.length);
    audible = this.playbackTail > 0;
    if (audible !== this.playing) {
      this.playing = audible;
      this.port.postMessage({ type: 'playback', active: audible });
    }
    return true;
  }
}
registerProcessor('live-voice-audio', LiveVoiceAudio);
