import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LiveVoiceConnection } from '@/lib/live-voice';

const mock = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('@/lib/api', () => ({ apiRequest: mock.request }));

class Socket {
  static OPEN = 1;
  static last: Socket;
  readyState = 1;
  bufferedAmount = 0;
  binaryType = '';
  sent: unknown[] = [];
  onopen?: () => void;
  onmessage?: (event: { data: unknown }) => void;
  onclose?: () => void;
  onerror?: () => void;
  constructor(public url: URL) { Socket.last = this; }
  send(value: unknown) { this.sent.push(value); }
  close() { this.readyState = 3; this.onclose?.(); }
}
class Context {
  sampleRate = 24000;
  destination = {};
  audioWorklet = { addModule: vi.fn().mockResolvedValue(undefined) };
  resume = vi.fn().mockResolvedValue(undefined);
  close = vi.fn().mockResolvedValue(undefined);
  createMediaStreamSource = () => ({ connect: vi.fn(), disconnect: vi.fn() });
}
class Processor {
  static last: Processor;
  port = { onmessage: null as null | ((event: { data: unknown }) => void), postMessage: vi.fn() };
  constructor() { Processor.last = this; }
  connect = vi.fn();
  disconnect = vi.fn();
}

beforeEach(() => {
  vi.stubGlobal('isSecureContext', true);
  vi.stubGlobal('AudioContext', Context);
  vi.stubGlobal('AudioWorkletNode', Processor);
  vi.stubGlobal('WebSocket', Socket);
  mock.request.mockResolvedValue({ ticket: 'one-use-ticket' });
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

function media(promise?: Promise<MediaStream>) {
  const track = { stop: vi.fn(), enabled: true, addEventListener: vi.fn() };
  const stream = { getTracks: () => [track], getAudioTracks: () => [track] } as unknown as MediaStream;
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: vi.fn().mockReturnValue(promise || Promise.resolve(stream)) } });
  return { stream, track };
}

describe('live voice lifecycle', () => {
  it('streams only after ready, continues capture during output and waits for final stop', async () => {
    const { track } = media(); const listener = vi.fn(); const voice = new LiveVoiceConnection(listener);
    await voice.start(async () => '/studio/voice/sessions');
    const ws = Socket.last; ws.onopen?.();
    expect(ws.url.search).toBe(''); expect(ws.sent).toEqual(['one-use-ticket']);
    Processor.last.port.onmessage?.({ data: { type: 'audio', buffer: new ArrayBuffer(960) } });
    expect(ws.sent.length).toBe(1);
    ws.onmessage?.({ data: JSON.stringify({ type: 'ready' }) });
    ws.onmessage?.({ data: new ArrayBuffer(960) });
    Processor.last.port.onmessage?.({ data: { type: 'audio', buffer: new ArrayBuffer(960) } });
    expect(ws.sent.length).toBe(2);
    voice.mute(true); expect(track.enabled).toBe(false);
    voice.stop(); expect(track.stop).toHaveBeenCalled(); expect(ws.readyState).toBe(1);
    expect(ws.sent.at(-1)).toBe('{"type":"stop"}');
    ws.onmessage?.({ data: JSON.stringify({ type: 'stopped' }) });
    expect(ws.readyState).toBe(3); expect(listener).toHaveBeenCalledWith({ type: 'stopped' });
  });

  it('releases a microphone resolved after cancellation without opening a session', async () => {
    let resolve!: (stream: MediaStream) => void;
    const pending = new Promise<MediaStream>(r => { resolve = r; });
    const { stream, track } = media(pending);
    const endpoint = vi.fn().mockResolvedValue('/studio/voice/sessions');
    const voice = new LiveVoiceConnection(vi.fn()); const start = voice.start(endpoint);
    await Promise.resolve(); voice.close(); resolve(stream); await start;
    expect(track.stop).toHaveBeenCalled(); expect(endpoint).not.toHaveBeenCalled();
  });

  it('fails on backpressure and releases the microphone instead of queuing delayed speech', async () => {
    const { track } = media(); const listener = vi.fn(); const voice = new LiveVoiceConnection(listener);
    await voice.start(async () => '/studio/voice/sessions');
    Socket.last.onmessage?.({ data: JSON.stringify({ type: 'ready' }) });
    Socket.last.bufferedAmount = 50000;
    Processor.last.port.onmessage?.({ data: { type: 'audio', buffer: new ArrayBuffer(960) } });
    expect(listener).toHaveBeenCalledWith(expect.objectContaining({ type: 'error' }));
    expect(track.stop).toHaveBeenCalled();
  });
});
