/**
 * useOrbAudio.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Spec §4 — Orb Sound System
 *
 * Called from inside the Three.js Orb component (useFrame context).
 * Provides:
 *   • Continuous idle breathing sync (pulse tied to orb's visual breath)
 *   • Voice-reactive frequency swell (audioLevel → orb resonance)
 *   • Intelligence tick pattern (while thinking)
 *   • Orb shimmer that follows visual ring rotation speed
 *
 * Uses Tone.js for the continuous oscillating tones (cleaner looping
 * than raw AudioBufferSourceNode for indefinite sounds).
 * ─────────────────────────────────────────────────────────────────────────────
 */
import { useEffect, useRef } from "react";
import { useZendaya } from "../store/zendayaStore";
import { AudioManager } from "../systems/AudioManager";
// Thinking-mode data-scan tick interval (ms)
const SCAN_TICK_INTERVAL_MS = 320;
export function useOrbAudio() {
    const shimmerOscRef = useRef(null);
    const shimmerGainRef = useRef(null);
    const prevAiRef = useRef("");
    // ── Set up persistent shimmer oscillator ─────────────────────────────────
    useEffect(() => {
        const ctx = AudioManager.ctx;
        if (!ctx)
            return;
        const layerGain = AudioManager.getLayerGain("orb");
        if (!layerGain)
            return;
        // Shimmer: very quiet high-freq oscillator, amplitude modulated by LFO
        const shimmerOsc = ctx.createOscillator();
        shimmerOsc.type = "sine";
        shimmerOsc.frequency.value = 2400;
        const lfo = ctx.createOscillator();
        lfo.type = "sine";
        lfo.frequency.value = 1.8; // 1.8 Hz breathe — syncs roughly with visual pulse
        const lfoGain = ctx.createGain();
        lfoGain.gain.value = 0.025; // very subtle amplitude mod
        const shimmerGain = ctx.createGain();
        shimmerGain.gain.value = 0.018;
        lfo.connect(lfoGain);
        lfoGain.connect(shimmerGain.gain);
        shimmerOsc.connect(shimmerGain);
        shimmerGain.connect(layerGain);
        shimmerOsc.start();
        lfo.start();
        shimmerOscRef.current = shimmerOsc;
        shimmerGainRef.current = shimmerGain;
        return () => {
            try {
                shimmerOsc.stop();
            }
            catch { /* */ }
            try {
                lfo.stop();
            }
            catch { /* */ }
        };
    }, []);
    // ── React to AI state for shimmer behavior ────────────────────────────────
    useEffect(() => {
        const unsub = useZendaya.subscribe((state) => {
            const ai = state.ai;
            if (ai === prevAiRef.current)
                return;
            prevAiRef.current = ai;
            const ctx = AudioManager.ctx;
            if (!ctx)
                return;
            // Adjust shimmer frequency per state (spec §4)
            if (shimmerOscRef.current) {
                const t = ctx.currentTime;
                const freqMap = {
                    idle: 2400,
                    listening: 3200, // pitch rises when listening
                    thinking: 2800,
                    speaking: 2000, // warmer, lower
                    error: 1400,
                };
                shimmerOscRef.current.frequency.setTargetAtTime(freqMap[ai] ?? 2400, t, 0.3);
            }
            // Start/stop thinking scan ticks
            if (ai === "thinking") {
                _startScanTicks();
            }
            else {
                _stopScanTicks();
            }
        });
        return () => {
            unsub();
            _stopScanTicks();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    // ── Voice-reactive: swell shimmer gain with audioLevel ───────────────────
    useEffect(() => {
        const unsub = useZendaya.subscribe((state) => {
            const level = state.audioLevel;
            const ctx = AudioManager.ctx;
            if (!ctx || !shimmerGainRef.current)
                return;
            // Swell amplitude — orb resonates with voice (spec §4 "Frequency swell")
            const target = 0.018 + level * 0.08;
            shimmerGainRef.current.gain.setTargetAtTime(target, ctx.currentTime, 0.05);
        });
        return () => unsub();
    }, []);
    return null;
}
// Module-level scan tick helpers (avoid closure issues with refs in effects)
let _scanTimer = null;
function _startScanTicks() {
    if (_scanTimer !== null)
        return;
    const tick = () => {
        const ctx = AudioManager.ctx;
        if (!ctx)
            return;
        const layerGain = AudioManager.getLayerGain("intelligence");
        if (!layerGain)
            return;
        const g = ctx.createGain();
        const osc = ctx.createOscillator();
        osc.type = "sine";
        // Random frequency from a pentatonic set — always sounds musical
        const pentatonic = [220, 277, 330, 440, 554, 660];
        osc.frequency.value = pentatonic[Math.floor(Math.random() * pentatonic.length)];
        osc.connect(g);
        g.connect(layerGain);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0.05, t);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.12);
        osc.start(t);
        osc.stop(t + 0.14);
        _scanTimer = window.setTimeout(tick, SCAN_TICK_INTERVAL_MS + Math.random() * 120);
    };
    _scanTimer = window.setTimeout(tick, 80);
}
function _stopScanTicks() {
    if (_scanTimer !== null) {
        clearTimeout(_scanTimer);
        _scanTimer = null;
    }
}
