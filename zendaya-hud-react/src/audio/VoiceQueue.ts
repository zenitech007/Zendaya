/**
 * VoiceQueue.ts — plays the backend's teed TTS PCM in the browser, gaplessly.
 *
 * Owns its own AudioContext (separate from the SFX/ambient AudioManager) so
 * voice routing stays simple and decoupled. Fed one base64 PCM window at a
 * time from useWebSocket. Chunks are scheduled back-to-back via nextStartTime
 * so there are no clicks between windows. Chunks whose id != the current
 * utterance are dropped (barge-in stragglers / late-joiner echoes).
 */
import { decodeBase64ToInt16, int16ToFloat32 } from "./pcmPlayer";

type AudioMsg =
  | { event: "begin"; rate: number; id: number }
  | { event: "chunk"; id: number; seq: number; b64: string }
  | { event: "end"; id: number }
  | { event: "stop" }
  | { event?: string; [k: string]: unknown };

export class VoiceQueue {
  private factory: () => AudioContext;
  private ctx: AudioContext | null = null;
  private currentId: number | null = null;
  private rate = 22050;
  private nextStartTime = 0;
  private active = new Set<AudioBufferSourceNode>();

  constructor(factory: () => AudioContext = () => new AudioContext()) {
    this.factory = factory;
  }

  private ensureCtx(): AudioContext {
    if (!this.ctx) this.ctx = this.factory();
    return this.ctx;
  }

  /** Resume the context on a user gesture (autoplay policy). Safe to call repeatedly. */
  unlock(): void {
    let ctx: AudioContext;
    try {
      ctx = this.ensureCtx();
    } catch {
      return; // no Web Audio available (e.g. test env without a factory)
    }
    if (ctx.state === "suspended") {
      try { ctx.resume().catch(() => {}); } catch { /* ignore */ }
    }
  }

  /** Route one wire frame. Tolerant of unknown/garbage shapes. */
  handle(msg: AudioMsg): void {
    switch (msg?.event) {
      case "begin":
        this.begin((msg as any).rate, (msg as any).id);
        break;
      case "chunk":
        this.push((msg as any).id, (msg as any).b64);
        break;
      case "end":
        this.end((msg as any).id);
        break;
      case "stop":
        this.stop();
        break;
      default:
        break;
    }
  }

  private begin(rate: number, id: number): void {
    let ctx: AudioContext;
    try {
      ctx = this.ensureCtx();
    } catch {
      return;
    }
    this.currentId = id;
    this.rate = rate > 0 ? rate : 22050;
    this.nextStartTime = ctx.currentTime;
  }

  private push(id: number, b64: string): void {
    if (this.currentId === null || id !== this.currentId) return;
    let ctx: AudioContext;
    try {
      ctx = this.ensureCtx();
    } catch {
      return;
    }
    const int16 = decodeBase64ToInt16(b64);
    if (int16.length === 0) return;
    const f32 = int16ToFloat32(int16);

    const buf = ctx.createBuffer(1, f32.length, this.rate);
    buf.getChannelData(0).set(f32);

    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);

    const startAt = Math.max(this.nextStartTime, ctx.currentTime);
    try { src.start(startAt); } catch { /* already started / closed */ }
    this.nextStartTime = startAt + buf.duration;

    this.active.add(src);
    src.onended = () => { this.active.delete(src); };
  }

  private end(id: number): void {
    if (id !== this.currentId) return;
    // Let already-scheduled buffers finish; nothing to do here. A later
    // begin/stop resets state. (Kept as a hook for future fades.)
  }

  private stop(): void {
    this.currentId = null;
    this.active.forEach((s) => { try { s.stop(); } catch { /* ignore */ } });
    this.active.clear();
    this.nextStartTime = this.ctx ? this.ctx.currentTime : 0;
  }
}
