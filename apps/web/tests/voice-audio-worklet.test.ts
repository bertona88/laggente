import source from '../lib/voice-audio-worklet.js?raw';
import { runInNewContext } from 'node:vm';
import { describe, expect, it } from 'vitest';

interface Processor {
  port: { onmessage: (event: { data: { type: string; buffer?: ArrayBuffer } }) => void };
  process(inputs: Float32Array[][], outputs: Float32Array[][]): boolean;
}
function worklet() {
  const events: { type: string }[] = [];
  let Constructor!: new () => Processor;
  runInNewContext(source, {
    sampleRate: 24000,
    AudioWorkletProcessor: class {
      port = { postMessage: (event: { type: string }) => events.push(event) };
    },
    registerProcessor: (_name: string, implementation: typeof Constructor) => { Constructor = implementation; },
  });
  const processor = new Constructor();
  processor.port.onmessage({ data: { type: 'start' } });
  return { processor, events };
}

describe('voice playback jitter buffer', () => {
  it('plays a two-second network burst in order while capture continues', () => {
    const { processor, events } = worklet();
    const samples = new Int16Array(48000);
    samples.fill(16384, 0, 24000); samples.fill(-16384, 24000);
    processor.port.onmessage({ data: { type: 'audio', buffer: samples.buffer } });
    const playback = new Float32Array(48000);
    processor.process([[new Float32Array(48000)]], [[playback]]);
    expect(playback[0]).toBe(0.5); expect(playback[23999]).toBe(0.5);
    expect(playback[24000]).toBe(-0.5); expect(playback[47999]).toBe(-0.5);
    expect(events.filter(event => event.type === 'audio')).toHaveLength(100);
    expect(events.some(event => event.type === 'overflow')).toBe(false);
  });
  it('rejects sustained backlog and stops output immediately', () => {
    const { processor, events } = worklet();
    processor.port.onmessage({ data: { type: 'audio', buffer: new Int16Array(144000).buffer } });
    expect(events.some(event => event.type === 'overflow')).toBe(true);
    const playback = new Float32Array(128).fill(1);
    processor.process([], [[playback]]);
    expect(playback.every(value => value === 0)).toBe(true);
  });
});
