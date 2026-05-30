/**
 * useSpatialAudio.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Spec §8 — Spatial Audio Architecture
 *
 * Exposes helpers for Three.js components that need positional audio:
 *   • useOrbPositionalAudio  — center-focused orb audio
 *   • useNotificationPan     — directional notification panning
 *   • useMapAudioSpread      — wide stereo for map scene
 *
 * Also provides useInteractionSound() — a simple hook any HUD button
 * can call to play spec-accurate interaction sounds (hover, click, etc.)
 * ─────────────────────────────────────────────────────────────────────────────
 */
import { useCallback } from "react";
import { SynthEngine } from "../systems/SynthEngine";
import { SpatialAudioEngine } from "../systems/SpatialAudioEngine";
import { AudioManager } from "../systems/AudioManager";
export function useInteractionSound() {
    const play = useCallback((type) => {
        // Resume context if suspended (browser autoplay)
        AudioManager.resume();
        SynthEngine.playInteraction(type);
    }, []);
    return { play };
}
// ── Notification directional ping ─────────────────────────────────────────────
let _notifPingDir = 0.4; // alternate left/right
export function useNotificationSound() {
    const playNotification = useCallback(() => {
        AudioManager.resume();
        // Alternate panning direction for each notification (spec §8: directional)
        const dir = _notifPingDir;
        _notifPingDir = -_notifPingDir;
        SynthEngine.playNotificationPing();
        // Play a second, directionally panned version for spatial feel
        const ctx = AudioManager.ctx;
        if (!ctx)
            return;
        const layerGain = AudioManager.getLayerGain("alert");
        if (!layerGain)
            return;
        const panner = ctx.createStereoPanner();
        panner.pan.value = dir;
        const g = ctx.createGain();
        g.gain.value = 0.08;
        panner.connect(g);
        g.connect(layerGain);
        // Small tick at the panned position
        const osc = ctx.createOscillator();
        osc.type = "sine";
        osc.frequency.value = 1200;
        osc.connect(panner);
        const t = ctx.currentTime;
        g.gain.setValueAtTime(0.08, t);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.12);
        osc.start(t);
        osc.stop(t + 0.13);
    }, []);
    return { playNotification };
}
// ── Map audio — wide environmental spread ─────────────────────────────────────
export function useMapAudio() {
    const onMapOpen = useCallback(() => {
        AudioManager.resume();
        // Widen ambient layer during map mode
        AudioManager.setLayerGain("ambient", 0.45);
        SynthEngine.playTransitionSweep("expand");
    }, []);
    const onMapClose = useCallback(() => {
        AudioManager.resume();
        AudioManager.resetLayerGain("ambient");
        SynthEngine.playTransitionSweep("contract");
    }, []);
    return { onMapOpen, onMapClose };
}
// ── Alert sounds ──────────────────────────────────────────────────────────────
export function useAlertSound() {
    const playAlert = useCallback((type) => {
        AudioManager.resume();
        SynthEngine.playAlert(type);
    }, []);
    return { playAlert };
}
// ── Spatial drift state for the orb ──────────────────────────────────────────
export function useOrbDrift() {
    const startDrift = useCallback(() => {
        SpatialAudioEngine.startOrbDrift();
    }, []);
    const stopDrift = useCallback(() => {
        SpatialAudioEngine.stopOrbDrift();
    }, []);
    return { startDrift, stopDrift };
}
