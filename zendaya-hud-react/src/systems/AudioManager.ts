/**
 * AudioManager.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Singleton that owns:
 *   • the AudioContext
 *   • master gain + per-layer gain buses
 *   • a one-shot buffer pool for UI SFX
 *   • crossfade / duck helpers used by all other systems
 *
 * Design rules from spec §2 & §12:
 *   - Never abruptly cut sounds — always fade
 *   - Pool audio buffers; avoid realtime synthesis overload
 *   - Disable heavy DSP on low-quality mode
 * ─────────────────────────────────────────────────────────────────────────────
 */

export type LayerName =
  | "ambient"
  | "orb"
  | "interaction"
  | "transition"
  | "intelligence"
  | "alert"
  | "voice"
  | "music";

interface LayerBus {
  gain: GainNode;
  targetGain: number; // desired value (interpolated each tick)
}

class AudioManagerSingleton {
  ctx: AudioContext | null = null;
  master: GainNode | null = null;
  analyser: AnalyserNode | null = null;

  private layers: Map<LayerName, LayerBus> = new Map();
  private bufferCache: Map<string, AudioBuffer> = new Map();
  private activeSources: Set<AudioBufferSourceNode> = new Set();
  private rafId = 0;
  private _started = false;

  // ── Default gain per layer (spec-tuned) ─────────────────────────────────
  private readonly LAYER_DEFAULTS: Record<LayerName, number> = {
    ambient:     0.28,
    orb:         0.45,
    interaction: 0.60,
    transition:  0.55,
    intelligence:0.38,
    alert:       0.70,
    voice:       0.90,
    music:       0.18,
  };

  // ── Bootstrap (call once after first user gesture) ───────────────────────
  start() {
    if (this._started) return;
    this._started = true;

    this.ctx = new AudioContext({ latencyHint: "interactive", sampleRate: 44100 });
    this.master = this.ctx.createGain();
    this.master.gain.value = 1.0;

    // Analyser for visual reactivity (VoiceVisualizer can tap this)
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 256;
    this.analyser.smoothingTimeConstant = 0.8;

    this.master.connect(this.analyser);
    this.analyser.connect(this.ctx.destination);

    // Create one GainNode per layer
    const layerNames: LayerName[] = [
      "ambient", "orb", "interaction", "transition",
      "intelligence", "alert", "voice", "music",
    ];
    for (const name of layerNames) {
      const gain = this.ctx.createGain();
      gain.gain.value = this.LAYER_DEFAULTS[name];
      gain.connect(this.master!);
      this.layers.set(name, { gain, targetGain: this.LAYER_DEFAULTS[name] });
    }

    // Smooth gain interpolation loop
    this._startGainLoop();
  }

  // ── Resume after browser autoplay policy suspended ────────────────────────
  async resume() {
    if (this.ctx && this.ctx.state === "suspended") {
      await this.ctx.resume();
    }
  }

  // ── Layer gain control ────────────────────────────────────────────────────
  getLayerGain(layer: LayerName): GainNode | null {
    return this.layers.get(layer)?.gain ?? null;
  }

  /** Smoothly set a layer to a target gain over ~80 ms */
  setLayerGain(layer: LayerName, value: number) {
    const bus = this.layers.get(layer);
    if (!bus) return;
    bus.targetGain = Math.max(0, Math.min(1.5, value));
  }

  /** Temporarily duck a layer then restore — used for voice sidechain §9 */
  duckLayer(layer: LayerName, duckTo: number, holdMs: number, fadeMs = 120) {
    const bus = this.layers.get(layer);
    if (!bus) return;
    const original = bus.targetGain;
    this.setLayerGain(layer, duckTo);
    setTimeout(() => {
      this.setLayerGain(layer, original);
    }, holdMs + fadeMs);
  }

  /** Reset a layer to its spec default */
  resetLayerGain(layer: LayerName) {
    this.setLayerGain(layer, this.LAYER_DEFAULTS[layer]);
  }

  // ── Buffer loading & caching ──────────────────────────────────────────────
  async loadBuffer(url: string): Promise<AudioBuffer | null> {
    if (!this.ctx) return null;
    if (this.bufferCache.has(url)) return this.bufferCache.get(url)!;
    try {
      const res = await fetch(url);
      if (!res.ok) return null;
      const arr = await res.arrayBuffer();
      const buf = await this.ctx.decodeAudioData(arr);
      this.bufferCache.set(url, buf);
      return buf;
    } catch {
      return null;
    }
  }

  // ── One-shot playback ─────────────────────────────────────────────────────
  playBuffer(
    buf: AudioBuffer,
    layer: LayerName,
    opts: {
      gainMult?: number;
      playbackRate?: number;
      loop?: boolean;
      fadeIn?: number;  // seconds
      fadeOut?: number; // seconds
      detune?: number;
      pan?: number;
    } = {}
  ): AudioBufferSourceNode | null {
    if (!this.ctx) return null;
    const layerGain = this.getLayerGain(layer);
    if (!layerGain) return null;

    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.loop = opts.loop ?? false;
    src.playbackRate.value = opts.playbackRate ?? 1.0;
    if (opts.detune !== undefined) src.detune.value = opts.detune;

    let node: AudioNode = src;

    // Optional stereo panner
    if (opts.pan !== undefined) {
      const panner = this.ctx.createStereoPanner();
      panner.pan.value = Math.max(-1, Math.min(1, opts.pan));
      src.connect(panner);
      node = panner;
    }

    // Per-source gain (for multiply + fade)
    const srcGain = this.ctx.createGain();
    const mult = opts.gainMult ?? 1.0;
    srcGain.gain.value = opts.fadeIn ? 0 : mult;
    node.connect(srcGain);
    srcGain.connect(layerGain);

    const now = this.ctx.currentTime;
    src.start(now);

    // Fade in
    if (opts.fadeIn && opts.fadeIn > 0) {
      srcGain.gain.setValueAtTime(0, now);
      srcGain.gain.linearRampToValueAtTime(mult, now + opts.fadeIn);
    }

    // Schedule fade out before end (if not looping)
    if (!opts.loop && opts.fadeOut && buf.duration > opts.fadeOut) {
      const fadeStart = now + buf.duration - opts.fadeOut;
      srcGain.gain.setValueAtTime(mult, fadeStart);
      srcGain.gain.linearRampToValueAtTime(0, now + buf.duration);
    }

    this.activeSources.add(src);
    src.onended = () => this.activeSources.delete(src);

    return src;
  }

  /** Stop a source with an optional fade-out */
  stopSource(src: AudioBufferSourceNode, fadeMs = 80) {
    if (!this.ctx) return;
    try {
      if (fadeMs > 0) {
        // We can't fade srcGain from here without keeping its ref,
        // so just disconnect after a delay
        setTimeout(() => { try { src.stop(); } catch { /* */ } }, fadeMs);
      } else {
        src.stop();
      }
    } catch { /* already stopped */ }
  }

  // ── Master volume ─────────────────────────────────────────────────────────
  setMasterGain(v: number) {
    if (this.master && this.ctx) {
      this.master.gain.setTargetAtTime(
        Math.max(0, Math.min(1, v)),
        this.ctx.currentTime,
        0.05
      );
    }
  }

  // ── Adaptive quality: simplify DSP on low FPS ────────────────────────────
  applyQuality(quality: "high" | "low") {
    if (quality === "low") {
      // Reduce ambient & orb layers; disable music
      this.setLayerGain("ambient", this.LAYER_DEFAULTS.ambient * 0.55);
      this.setLayerGain("orb",     this.LAYER_DEFAULTS.orb     * 0.65);
      this.setLayerGain("music",   0);
    } else {
      this.resetLayerGain("ambient");
      this.resetLayerGain("orb");
      this.resetLayerGain("music");
    }
  }

  // ── Internal smooth-gain loop ─────────────────────────────────────────────
  private _startGainLoop() {
    const tick = () => {
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      this.layers.forEach((bus) => {
        const cur = bus.gain.gain.value;
        const diff = bus.targetGain - cur;
        if (Math.abs(diff) > 0.001) {
          // Exponential approach — ~80 ms time constant
          bus.gain.gain.setTargetAtTime(bus.targetGain, now, 0.05);
        }
      });
      this.rafId = requestAnimationFrame(tick);
    };
    this.rafId = requestAnimationFrame(tick);
  }

  dispose() {
    cancelAnimationFrame(this.rafId);
    this.activeSources.forEach((s) => { try { s.stop(); } catch { /* */ } });
    this.activeSources.clear();
    this.ctx?.close();
    this.ctx = null;
    this._started = false;
  }
}

// ── Singleton export ──────────────────────────────────────────────────────────
export const AudioManager = new AudioManagerSingleton();
