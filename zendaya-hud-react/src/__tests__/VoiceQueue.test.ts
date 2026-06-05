import { describe, expect, it, vi } from "vitest";
import { VoiceQueue } from "../audio/VoiceQueue";
import { int16ToFloat32 } from "../audio/pcmPlayer";

// base64 of N little-endian int16 zero samples (silence is fine for scheduling math).
function b64Zeros(sampleCount: number): string {
  const bytes = new Uint8Array(sampleCount * 2); // all zero
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s);
}

class FakeBufferSource {
  buffer: any = null;
  onended: (() => void) | null = null;
  started: number | null = null;
  stopped = false;
  failStart = false;
  connect = vi.fn();
  start = vi.fn((t: number) => {
    if (this.failStart) throw new Error("start failed");
    this.started = t;
  });
  stop = vi.fn(() => { this.stopped = true; });
}

class FakeAudioContext {
  currentTime = 10; // non-zero so we can see scheduling offsets
  sampleRate = 48000;
  state: AudioContextState = "running";
  destination = {} as AudioNode;
  sources: FakeBufferSource[] = [];
  buffers: any[] = [];
  failNextStart = false;

  createBuffer(_channels: number, length: number, rate: number) {
    const data = new Float32Array(length);
    const buf = {
      length,
      sampleRate: rate,
      duration: length / rate,
      getChannelData: () => data,
    };
    this.buffers.push(buf);
    return buf as unknown as AudioBuffer;
  }
  createBufferSource() {
    const s = new FakeBufferSource();
    if (this.failNextStart) {
      s.failStart = true;
      this.failNextStart = false;
    }
    this.sources.push(s);
    return s as unknown as AudioBufferSourceNode;
  }
  resume() { this.state = "running"; return Promise.resolve(); }
  close() { return Promise.resolve(); }
}

function makeQueue() {
  const ctx = new FakeAudioContext();
  const q = new VoiceQueue(() => ctx as unknown as AudioContext);
  return { ctx, q };
}

describe("VoiceQueue", () => {
  it("schedules a chunk to start at the context's current time", () => {
    const { ctx, q } = makeQueue();
    q.handle({ event: "begin", rate: 22050, id: 1 });
    q.handle({ event: "chunk", id: 1, seq: 0, b64: b64Zeros(22050) }); // 1.0 s
    expect(ctx.sources.length).toBe(1);
    expect(ctx.sources[0].started).toBeCloseTo(10, 5);
  });

  it("plays chunks gaplessly (next starts where previous ends)", () => {
    const { ctx, q } = makeQueue();
    q.handle({ event: "begin", rate: 22050, id: 1 });
    q.handle({ event: "chunk", id: 1, seq: 0, b64: b64Zeros(22050) }); // 1.0 s @22050
    q.handle({ event: "chunk", id: 1, seq: 1, b64: b64Zeros(11025) }); // 0.5 s @22050
    expect(ctx.sources.length).toBe(2);
    expect(ctx.sources[0].started).toBeCloseTo(10, 5);
    // second starts at 10 + 1.0 = 11.0 (buffer made at the 22050 rate, not ctx rate)
    expect(ctx.sources[1].started).toBeCloseTo(11, 5);
  });

  it("ignores chunks from a stale utterance id", () => {
    const { ctx, q } = makeQueue();
    q.handle({ event: "begin", rate: 22050, id: 2 });
    q.handle({ event: "chunk", id: 1, seq: 0, b64: b64Zeros(100) }); // stale id
    expect(ctx.sources.length).toBe(0);
  });

  it("ignores a chunk that arrives before any begin", () => {
    const { ctx, q } = makeQueue();
    q.handle({ event: "chunk", id: 1, seq: 0, b64: b64Zeros(100) });
    expect(ctx.sources.length).toBe(0);
  });

  it("stop() halts and clears all active sources", () => {
    const { ctx, q } = makeQueue();
    q.handle({ event: "begin", rate: 22050, id: 1 });
    q.handle({ event: "chunk", id: 1, seq: 0, b64: b64Zeros(22050) });
    const src = ctx.sources[0];
    q.handle({ event: "stop" });
    expect(src.stopped).toBe(true);
    // a subsequent chunk for the stopped utterance is ignored
    q.handle({ event: "chunk", id: 1, seq: 1, b64: b64Zeros(22050) });
    expect(ctx.sources.length).toBe(1);
  });

  it("uses the buffer's PCM data from the decoded base64", () => {
    const { ctx, q } = makeQueue();
    q.handle({ event: "begin", rate: 22050, id: 1 });
    q.handle({ event: "chunk", id: 1, seq: 0, b64: b64Zeros(4) });
    // int16ToFloat32 of zeros is zeros — buffer length should match sample count
    expect(ctx.buffers[0].length).toBe(4);
    expect(Array.from(int16ToFloat32(Int16Array.from([0, 0])))).toEqual([0, 0]);
  });

  it("duplicate begin with the same id does not reset the timeline", () => {
    const { ctx, q } = makeQueue();
    // First begin (id=7) + first chunk (22050 samples @ 22050 Hz = 1.0 s)
    q.handle({ event: "begin", rate: 22050, id: 7 });
    q.handle({ event: "chunk", id: 7, seq: 0, b64: b64Zeros(22050) }); // 1.0 s
    // nextStartTime is now 10 + 1.0 = 11.0
    const expectedFirstEnd = 10 + 22050 / 22050; // 11.0

    // Duplicate begin — same id, must be a no-op (does NOT reset nextStartTime)
    q.handle({ event: "begin", rate: 22050, id: 7 });

    // Second chunk (11025 samples @ 22050 Hz = 0.5 s) must start gaplessly at 11.0
    q.handle({ event: "chunk", id: 7, seq: 1, b64: b64Zeros(11025) }); // 0.5 s
    expect(ctx.sources.length).toBe(2);
    expect(ctx.sources[1].started).toBeCloseTo(expectedFirstEnd, 5);
  });

  it("a throwing start() does not advance the timeline or leak the source", () => {
    const { ctx, q } = makeQueue();
    q.handle({ event: "begin", rate: 22050, id: 9 });

    // Arm the fake so the next createBufferSource()'s start() will throw
    ctx.failNextStart = true;
    // Push a chunk whose start() throws — timeline must NOT advance
    q.handle({ event: "chunk", id: 9, seq: 0, b64: b64Zeros(22050) }); // would be 1.0 s
    const failingSource = ctx.sources[0];
    expect(failingSource.started).toBeNull(); // start() threw, so started was never set

    // Push a good second chunk — it must start at ctx.currentTime (10), NOT at 10+1
    q.handle({ event: "chunk", id: 9, seq: 1, b64: b64Zeros(11025) }); // 0.5 s
    const goodSource = ctx.sources[1];
    expect(goodSource.started).toBeCloseTo(10, 5); // timeline not advanced past the failed start

    // The failing source must NOT be in the active set — stop() must not call its stop()
    q.handle({ event: "stop" });
    expect(failingSource.stopped).toBe(false);
  });
});
