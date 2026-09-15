import { apiRequest } from '@/lib/api';

export type VoiceEvent =
  | { type: 'ready' | 'stopped' }
  | { type: 'working'; active: boolean }
  | { type: 'playback'; active: boolean }
  | { type: 'level'; value: number }
  | { type: 'error'; message: string }
  | { type: 'transcript'; speaker: 'user' | 'assistant'; event_id: string; session_id: string; created_at: string; delta: string; start_ms: number; end_ms: number };

export class LiveVoiceConnection {
  private socket: WebSocket | null = null;
  private stream: MediaStream | null = null;
  private context: AudioContext | null = null;
  private processor: AudioWorkletNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private ended = false;
  private stopping = false;
  private ready = false;
  private timeout: ReturnType<typeof setTimeout> | null = null;
  private abort = new AbortController();

  constructor(private onEvent: (event: VoiceEvent) => void) {}

  async start(endpoint: () => Promise<string>) {
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) {
        throw new Error('La voce richiede un browser aggiornato e una connessione sicura. Puoi continuare a scrivere.');
      }
      // Resume audio inside the click gesture, before awaiting microphone permission.
      this.context = new AudioContext({ sampleRate: 24000, latencyHint: 'interactive' });
      await this.context.resume();
      if (this.ended) return;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: {
        echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1,
      } });
      if (this.ended) { stream.getTracks().forEach(track => track.stop()); return; }
      this.stream = stream;
      this.timeout = setTimeout(() => this.fail('La connessione vocale non risponde. Riprova.'), 30000);
      stream.getTracks().forEach(track => track.addEventListener('ended', () => this.stop()));
      if (this.context.sampleRate !== 24000) throw new Error('Il browser non supporta questo formato audio. Puoi scrivere.');
      await this.context.audioWorklet.addModule(new URL('./voice-audio-worklet.js?no-inline', import.meta.url));
      if (this.ended) return;
      this.processor = new AudioWorkletNode(this.context, 'live-voice-audio', {
        numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1],
      });
      this.processor.onprocessorerror = () => this.fail('Il dispositivo audio si è fermato. Riprova.');
      this.context.onstatechange = () => {
        if (this.ready && !this.stopping && this.context?.state === 'suspended') this.stop();
      };
      this.source = this.context.createMediaStreamSource(stream);
      this.source.connect(this.processor);
      this.processor.connect(this.context.destination);
      await this.context.resume();
      if (this.ended) return;
      if (this.context.state === 'suspended') throw new Error('Il browser ha bloccato l’audio. Controlla i permessi del sito e riavvia la voce.');
      this.processor.port.onmessage = ({ data }) => {
        if (data.type === 'level') this.onEvent({ type: 'level', value: data.value });
        if (data.type === 'playback') this.onEvent({ type: 'playback', active: data.active });
        if (data.type === 'audio' && this.ready && !this.stopping && this.socket?.readyState === WebSocket.OPEN) {
          if (this.socket.bufferedAmount > 48000) { this.fail('La rete è troppo lenta per la voce. Riprova.'); return; }
          this.socket.send(data.buffer);
        } else if (data.type === 'overflow' || data.type === 'unsupported-rate') {
          this.fail('La riproduzione vocale si è interrotta. Riprova o continua a scrivere.');
        }
      };
      const path = await endpoint();
      if (this.ended) return;
      const session = await apiRequest<{ ticket: string }>(path, { method: 'POST', signal: this.abort.signal });
      if (this.ended) return;
      const url = new URL('/api/v1/voice/connect', window.location.href);
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      this.socket = new WebSocket(url);
      this.socket.binaryType = 'arraybuffer';
      this.socket.onopen = () => this.socket?.send(session.ticket);
      this.socket.onmessage = ({ data }) => {
        if (this.ended) return;
        if (data instanceof ArrayBuffer) {
          if (!this.stopping) this.processor?.port.postMessage({ type: 'audio', buffer: data }, [data]);
          return;
        }
        try {
          const event = JSON.parse(data) as VoiceEvent;
          if (event.type === 'ready') {
            this.ready = true;
            if (this.timeout) clearTimeout(this.timeout);
            this.timeout = null;
            this.processor?.port.postMessage({ type: 'start' });
          }
          if (event.type === 'error') { this.fail(event.message); return; }
          if (event.type === 'stopped') { this.close(); return; }
          this.onEvent(event);
        } catch { this.fail('Risposta vocale non valida. Riprova.'); }
      };
      this.socket.onerror = () => this.fail('La connessione vocale non è riuscita. Puoi continuare a scrivere.');
      this.socket.onclose = () => {
        if (!this.ended) this.fail('La connessione vocale si è interrotta. Puoi continuare a scrivere.');
      };
    } catch (error) {
      if (!this.ended) this.fail(error instanceof Error ? error.message : 'Microfono non disponibile.');
    }
  }

  mute(muted: boolean) {
    this.stream?.getAudioTracks().forEach(track => { track.enabled = !muted; });
    if (this.ready && !this.stopping) this.socket?.send(JSON.stringify({ type: muted ? 'mute' : 'unmute' }));
  }

  stop() {
    if (this.ended || this.stopping) return;
    this.stopping = true;
    // Stop local capture/playback immediately; keep receiving final transcripts and usage.
    this.stream?.getTracks().forEach(track => track.stop());
    this.processor?.port.postMessage({ type: 'stop' });
    if (this.ready && this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type: 'stop' }));
      if (this.timeout) clearTimeout(this.timeout);
      this.timeout = setTimeout(() => this.fail('Voce terminata; la conferma finale del server non è arrivata.'), 7000);
    } else this.close();
  }

  close() {
    if (this.ended) return;
    this.ended = true;
    this.abort.abort();
    if (this.timeout) clearTimeout(this.timeout);
    this.stream?.getTracks().forEach(track => track.stop());
    this.processor?.port.postMessage({ type: 'stop' });
    this.source?.disconnect();
    this.processor?.disconnect();
    void this.context?.close().catch(() => undefined);
    this.socket?.close();
    this.onEvent({ type: 'stopped' });
  }

  private fail(message: string) {
    if (this.ended) return;
    this.onEvent({ type: 'error', message });
    this.close();
  }
}
