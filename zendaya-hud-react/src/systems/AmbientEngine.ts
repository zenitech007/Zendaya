/**
 * AmbientEngine.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Spec §3 — Ambient Layer
 *
 * Creates the "always-on" atmospheric foundation:
 *   • Core Hum      — 40–120 Hz synthetic hum (AI presence)
 *   • Energy Texture — faint evolving electronic texture (computation feel)
 *   • Orbital Air    — very subtle slow stereo movement (depth/dimensionality)
 *
 * All layers loop indefinitely with slow LFO evolution.
 * Complexity can be reduced by AdaptiveAudioController.
 *
 * Spec rules:
 *   - Never silent
 *   - Slowly evolving, non-repetitive
 *   - Soft, wide, atmospheric
 *   - Reacts to AI state (increase during thinking, calm during idle)
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { AudioManager } from "./AudioManager";
import type { AmbientParams } from "./ambientParams";

type AmbientComplexity = "full" | "standard" | "reduced" | "minimal";

interface AmbientVoice {
  osc: OscillatorNode;
  gain: GainNode;
  lfo?: OscillatorNode;
  lfoGain?: GainNode;
}

class AmbientEngineSingleton {
  private voices: AmbientVoice[] = [];
  private orbitalPanner: StereoPannerNode | null = null;
  private orbitalLfo: OscillatorNode | null = null;
  private _running = false;

  // ── Start the ambient layer ───────────────────────────────────────────────
  start() {
    if (this._running) return;
    const ctx = AudioManager.ctx;
    if (!ctx) return;
    this._running = true;

    const layer = AudioManager.getLayerGain("ambient");
    if (!layer) return;

    // ── 1. Core Hum — 55 Hz fundamental + 3rd harmonic (spec: 40-120 Hz) ──
    this._addVoice(ctx, layer, {
      freq: 55,
      type: "sine",
      amp: 0.55,
      lfoFreq: 0.07,   // very slow breathe — ~14 s cycle
      lfoDepth: 6,     // Hz
    });

    // 2nd harmonic layer — gives thickness
    this._addVoice(ctx, layer, {
      freq: 110,
      type: "sine",
      amp: 0.25,
      lfoFreq: 0.11,
      lfoDepth: 8,
    });

    // ── 2. Energy Texture — higher noise-like content (spec §3) ────────────
    this._addVoice(ctx, layer, {
      freq: 220,
      type: "triangle",
      amp: 0.08,
      lfoFreq: 0.19,
      lfoDepth: 30,
      detune: 7,
    });

    // ── 3. Orbital Air Movement — panned stereo sweep (spec §3) ────────────
    this._addOrbitalAir(ctx, layer);
  }

  // ── Stop & clean up ───────────────────────────────────────────────────────
  stop() {
    this._running = false;
    this.voices.forEach(({ osc, gain, lfo }) => {
      const ctx = AudioManager.ctx;
      if (!ctx) return;
      const t = ctx.currentTime;
      gain.gain.setTargetAtTime(0, t, 0.5);
      setTimeout(() => {
        try { osc.stop(); } catch { /* */ }
        try { lfo?.stop(); } catch { /* */ }
      }, 1500);
    });
    this.voices = [];

    if (this.orbitalLfo) {
      try { this.orbitalLfo.stop(); } catch { /* */ }
      this.orbitalLfo = null;
    }
    if (this.orbitalPanner) {
      try { this.orbitalPanner.disconnect(); } catch { /* */ }
      this.orbitalPanner = null;
    }
  }

  // ── Adaptive complexity control ───────────────────────────────────────────
  setComplexity(c: AmbientComplexity) {
    const ctx = AudioManager.ctx;
    if (!ctx) return;
    const t = ctx.currentTime;

    // Adjust individual voice gains based on complexity
    const gains = this.voices.map((v) => v.gain);
    switch (c) {
      case "full":
        gains.forEach((g, i) => g.gain.setTargetAtTime([0.55, 0.25, 0.08][i] ?? 0.05, t, 0.5));
        if (this.orbitalPanner) this.orbitalPanner.pan.setTargetAtTime(0, t, 0.5);
        break;
      case "standard":
        gains.forEach((g, i) => g.gain.setTargetAtTime([0.50, 0.22, 0.07][i] ?? 0.04, t, 0.5));
        break;
      case "reduced":
        gains.forEach((g, i) => g.gain.setTargetAtTime([0.40, 0.15, 0.03][i] ?? 0.02, t, 0.5));
        break;
      case "minimal":
        // Only keep core hum, silence texture + orbital
        gains.forEach((g, i) => g.gain.setTargetAtTime([0.28, 0.08, 0][i] ?? 0, t, 1.0));
        if (this.orbitalPanner) this.orbitalPanner.pan.setTargetAtTime(0, t, 1.0);
        break;
    }
  }

  // ── Add a single oscillator voice with LFO modulation ────────────────────
  private _addVoice(
    ctx: AudioContext,
    layer: GainNode,
    opts: {
      freq: number;
      type: OscillatorType;
      amp: number;
      lfoFreq?: number;
      lfoDepth?: number;
      detune?: number;
    }
  ) {
    const osc = ctx.createOscillator();
    osc.type = opts.type;
    osc.frequency.value = opts.freq;
    if (opts.detune) osc.detune.value = opts.detune;

    const gain = ctx.createGain();
    gain.gain.value = 0;

    let lfo: OscillatorNode | undefined;
    let lfoGain: GainNode | undefined;

    if (opts.lfoFreq && opts.lfoDepth) {
      lfo = ctx.createOscillator();
      lfo.type = "sine";
      lfo.frequency.value = opts.lfoFreq;
      lfoGain = ctx.createGain();
      lfoGain.gain.value = opts.lfoDepth;
      lfo.connect(lfoGain);
      lfoGain.connect(osc.frequency);
      lfo.start();
    }

    osc.connect(gain);
    gain.connect(layer);
    osc.start();

    // Fade in slowly — spec: "slowly evolving"
    const t = ctx.currentTime;
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(opts.amp, t + 3.0);

    this.voices.push({ osc, gain, lfo, lfoGain });
  }

  // ── Orbital air movement — slow panning sine wave ─────────────────────────
  private _addOrbitalAir(ctx: AudioContext, layer: GainNode) {
    const osc = ctx.createOscillator();
    osc.type = "sine";
    osc.frequency.value = 180; // mid-air texture

    const gain = ctx.createGain();
    gain.gain.value = 0;

    this.orbitalPanner = ctx.createStereoPanner();
    this.orbitalPanner.pan.value = 0;

    // LFO drives the pan — very slow, ±0.15 (spec: subtle, not aggressive)
    this.orbitalLfo = ctx.createOscillator();
    this.orbitalLfo.type = "sine";
    this.orbitalLfo.frequency.value = 0.05; // ~20 s cycle
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = 0.15;
    this.orbitalLfo.connect(lfoGain);
    lfoGain.connect(this.orbitalPanner.pan);

    osc.connect(gain);
    gain.connect(this.orbitalPanner);
    this.orbitalPanner.connect(layer);

    osc.start();
    this.orbitalLfo.start();

    const t = ctx.currentTime;
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(0.04, t + 4.0); // very quiet

    this.voices.push({ osc, gain, lfo: this.orbitalLfo });
  }

  // ── Per-theme timbre — crossfade the voice bank to the active theme ───────
  // Voice order from start(): [0]=core hum, [1]=2nd harmonic, [2]=energy
  // texture, [3]=orbital air. setTargetAtTime gives a click-free glide.
  applyTheme(p: AmbientParams) {
    const ctx = AudioManager.ctx;
    if (!ctx || !this._running) return;
    const t = ctx.currentTime;
    const tau = 0.8; // ~0.8 s glide time-constant
    const [core, harm, tex, air] = this.voices;
    if (core) core.osc.frequency.setTargetAtTime(p.baseFreq, t, tau);
    if (harm) harm.osc.frequency.setTargetAtTime(p.baseFreq * 2, t, tau);
    if (tex) {
      tex.osc.frequency.setTargetAtTime(220 * p.brightness, t, tau);
      tex.gain.gain.setTargetAtTime(0.08 * p.harmonicMix, t, tau);
    }
    if (air) air.osc.frequency.setTargetAtTime(p.airFreq, t, tau);
  }

  get isRunning() { return this._running; }
}

export const AmbientEngine = new AmbientEngineSingleton();
