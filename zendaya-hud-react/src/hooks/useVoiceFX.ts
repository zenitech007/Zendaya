/**
 * useVoiceFX.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Spec §9 — Voice System Architecture
 *
 * Builds a Web Audio processing chain for Zendaya's TTS voice output:
 *   1. Subtle reverb   → spatial depth (not obvious echo)
 *   2. Harmonic exciter → futuristic clarity (high-shelf boost + saturation)
 *   3. Dynamic EQ      → smooth, premium voice texture
 *   4. Sidechain duck  → ambient lowers when speaking
 *
 * Returns { connectVoiceSource } — call with a MediaElementSourceNode
 * or AudioBufferSourceNode when TTS audio plays.
 *
 * Spec rules:
 *   - Calm, intelligent, warm, slightly synthetic
 *   - Very light reverb — avoid obvious echo
 *   - Ambience ducks when voice active
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useEffect, useRef, useCallback } from "react";
import { AudioManager } from "../systems/AudioManager";
import { useZendaya } from "../store/zendayaStore";

interface VoiceFXChain {
  input: GainNode;
  reverb: ConvolverNode;
  exciterFilter: BiquadFilterNode;
  eqLow: BiquadFilterNode;
  eqMid: BiquadFilterNode;
  eqHigh: BiquadFilterNode;
  output: GainNode;
}

function buildImpulseResponse(ctx: AudioContext, duration = 0.8, decay = 2.5): AudioBuffer {
  // Generate a synthetic reverb impulse (exponential decay noise)
  const sampleRate = ctx.sampleRate;
  const length = Math.floor(sampleRate * duration);
  const buffer = ctx.createBuffer(2, length, sampleRate);

  for (let channel = 0; channel < 2; channel++) {
    const data = buffer.getChannelData(channel);
    for (let i = 0; i < length; i++) {
      // Exponential decay on random noise
      data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, decay);
    }
  }
  return buffer;
}

export function useVoiceFX() {
  const chainRef = useRef<VoiceFXChain | null>(null);

  // ── Build the FX chain once AudioManager is ready ─────────────────────────
  useEffect(() => {
    const ctx = AudioManager.ctx;
    if (!ctx) return;

    const voiceGain = AudioManager.getLayerGain("voice");
    if (!voiceGain) return;

    // Input gain
    const input = ctx.createGain();
    input.gain.value = 1.0;

    // ── 1. Subtle Reverb (spec §9: "Very light — avoid obvious echo") ──────
    const reverb = ctx.createConvolver();
    reverb.buffer = buildImpulseResponse(ctx, 0.75, 3.0);

    // Reverb wet/dry mix — mostly dry (15% wet is enough for "subtle depth")
    const dryGain = ctx.createGain(); dryGain.gain.value = 0.85;
    const wetGain = ctx.createGain(); wetGain.gain.value = 0.15;
    input.connect(dryGain);
    input.connect(reverb); reverb.connect(wetGain);

    // ── 2. Harmonic Exciter (spec §9: "Futuristic clarity") ─────────────────
    // High-shelf boost above 6 kHz
    const exciterFilter = ctx.createBiquadFilter();
    exciterFilter.type = "highshelf";
    exciterFilter.frequency.value = 6000;
    exciterFilter.gain.value = 3.5;

    // ── 3. Dynamic EQ — three-band shaping (spec §9: "smooth and premium") ──
    const eqLow = ctx.createBiquadFilter();
    eqLow.type = "lowshelf";
    eqLow.frequency.value = 250;
    eqLow.gain.value = -2.0; // roll off low rumble

    const eqMid = ctx.createBiquadFilter();
    eqMid.type = "peaking";
    eqMid.frequency.value = 2500;
    eqMid.gain.value = 2.5;   // presence boost
    eqMid.Q.value = 0.8;

    const eqHigh = ctx.createBiquadFilter();
    eqHigh.type = "highshelf";
    eqHigh.frequency.value = 10000;
    eqHigh.gain.value = 1.5;  // air

    // ── Chain routing: input → dry+wet merge → exciter → EQ → voice layer ──
    const merge = ctx.createGain();
    dryGain.connect(merge);
    wetGain.connect(merge);

    merge.connect(exciterFilter);
    exciterFilter.connect(eqLow);
    eqLow.connect(eqMid);
    eqMid.connect(eqHigh);

    const output = ctx.createGain();
    output.gain.value = 1.0;
    eqHigh.connect(output);
    output.connect(voiceGain);

    chainRef.current = {
      input, reverb, exciterFilter,
      eqLow, eqMid, eqHigh, output,
    };

    return () => {
      try {
        input.disconnect();
        reverb.disconnect();
        dryGain.disconnect();
        wetGain.disconnect();
        merge.disconnect();
        exciterFilter.disconnect();
        eqLow.disconnect();
        eqMid.disconnect();
        eqHigh.disconnect();
        output.disconnect();
      } catch { /* */ }
      chainRef.current = null;
    };
  }, []);

  // ── Sidechain ducking when AI is speaking ────────────────────────────────
  useEffect(() => {
    const unsub = useZendaya.subscribe((state) => {
      if (state.ai === "speaking") {
        // Duck ambient -65% and orb -45% — voice gains focus (spec §9)
        AudioManager.duckLayer("ambient", 0.10, 10000, 300);
        AudioManager.duckLayer("orb",     0.25, 10000, 300);
      }
    });
    return () => unsub();
  }, []);

  // ── connectVoiceSource — attach any audio node to the FX chain ──────────
  const connectVoiceSource = useCallback((sourceNode: AudioNode): boolean => {
    if (!chainRef.current) return false;
    try {
      sourceNode.connect(chainRef.current.input);
      return true;
    } catch {
      return false;
    }
  }, []);

  return { connectVoiceSource };
}
