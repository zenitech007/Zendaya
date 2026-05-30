/**
 * SpatialAudioEngine.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Implements spec §8 — Spatial Audio Architecture
 *
 * Provides:
 *   • createPanner()       — full 3D PannerNode for positional audio
 *   • createStereoDrift()  — subtle slow stereo movement for orb / particles
 *   • directionalPing()    — left/right notification panning
 *   • wideEnvironment()    — wide stereo for map / environment layer
 *
 * Spec rules:
 *   - Orb: center-focused audio
 *   - Notifications: directional panning
 *   - Particles: subtle stereo drift
 *   - Map: wide environmental spread
 *   - Movement should feel floating, atmospheric, holographic
 *   - Avoid aggressive panning
 * ─────────────────────────────────────────────────────────────────────────────
 */
import { AudioManager } from "./AudioManager";
class SpatialAudioEngineSingleton {
    // Subtle stereo oscillation state (for particles / orb shimmer)
    driftPhase = 0;
    driftNode = null;
    driftRafId = 0;
    // ── Create a full 3D PannerNode (for positional sound in Three.js space) ──
    createPanner(opts = {}) {
        const ctx = AudioManager.ctx;
        if (!ctx)
            return null;
        const panner = ctx.createPanner();
        panner.panningModel = "HRTF";
        panner.distanceModel = "inverse";
        panner.refDistance = opts.refDistance ?? 1;
        panner.rolloffFactor = opts.rolloff ?? 0.8;
        panner.coneInnerAngle = 360;
        panner.coneOuterAngle = 0;
        panner.coneOuterGain = 0;
        panner.positionX.value = opts.posX ?? 0;
        panner.positionY.value = opts.posY ?? 0;
        panner.positionZ.value = opts.posZ ?? 0;
        return panner;
    }
    /** Update a panner's world position (call from Three.js useFrame) */
    updatePannerPosition(panner, x, y, z) {
        const ctx = AudioManager.ctx;
        if (!ctx || !panner)
            return;
        const t = ctx.currentTime;
        panner.positionX.setTargetAtTime(x, t, 0.05);
        panner.positionY.setTargetAtTime(y, t, 0.05);
        panner.positionZ.setTargetAtTime(z, t, 0.05);
    }
    /** Update listener position to match camera (call from useFrame) */
    updateListener(posX, posY, posZ, fwdX, fwdY, fwdZ, upX = 0, upY = 1, upZ = 0) {
        const ctx = AudioManager.ctx;
        if (!ctx?.listener)
            return;
        const l = ctx.listener;
        const t = ctx.currentTime;
        if (l.positionX) {
            l.positionX.setTargetAtTime(posX, t, 0.05);
            l.positionY.setTargetAtTime(posY, t, 0.05);
            l.positionZ.setTargetAtTime(posZ, t, 0.05);
            l.forwardX.setTargetAtTime(fwdX, t, 0.05);
            l.forwardY.setTargetAtTime(fwdY, t, 0.05);
            l.forwardZ.setTargetAtTime(fwdZ, t, 0.05);
            l.upX.setTargetAtTime(upX, t, 0.05);
            l.upY.setTargetAtTime(upY, t, 0.05);
            l.upZ.setTargetAtTime(upZ, t, 0.05);
        }
        else {
            // Older API fallback
            l.setPosition(posX, posY, posZ);
            l.setOrientation(fwdX, fwdY, fwdZ, upX, upY, upZ);
        }
    }
    // ── Subtle slow stereo drift (spec: "floating, atmospheric, holographic") ─
    /** Start a persistent slow drift on a StereoPannerNode */
    startOrbDrift() {
        const ctx = AudioManager.ctx;
        if (!ctx)
            return null;
        if (this.driftNode)
            return this.driftNode;
        this.driftNode = ctx.createStereoPanner();
        this.driftNode.pan.value = 0;
        this.driftNode.connect(AudioManager.getLayerGain("orb"));
        const tick = () => {
            if (!this.driftNode || !ctx)
                return;
            this.driftPhase += 0.0004; // very slow — full cycle ~15 s
            // Max pan ±0.12 — subtle, never aggressive
            const pan = Math.sin(this.driftPhase * Math.PI * 2) * 0.12;
            this.driftNode.pan.setTargetAtTime(pan, ctx.currentTime, 0.3);
            this.driftRafId = requestAnimationFrame(tick);
        };
        this.driftRafId = requestAnimationFrame(tick);
        return this.driftNode;
    }
    stopOrbDrift() {
        cancelAnimationFrame(this.driftRafId);
        if (this.driftNode) {
            try {
                this.driftNode.disconnect();
            }
            catch { /* */ }
            this.driftNode = null;
        }
    }
    // ── Directional notification pings (spec §8: "Notifications: directional") ─
    /**
     * Play a buffer with directional panning.
     * direction: -1 (left) … +1 (right), 0 = center
     */
    directionalPlay(buf, direction, gainMult = 1.0) {
        AudioManager.playBuffer(buf, "alert", {
            pan: Math.max(-1, Math.min(1, direction)) * 0.6, // never fully hard-pan
            gainMult,
            fadeIn: 0.015,
        });
    }
    // ── Wide environment stereo (spec §8: "Map: wide environmental spread") ──
    /** Apply a wide stereo spread to an existing audio node using two panners */
    createWideStereoSend(opts = {}) {
        const ctx = AudioManager.ctx;
        if (!ctx)
            return null;
        const spread = opts.spread ?? 0.55;
        const left = ctx.createStereoPanner();
        const right = ctx.createStereoPanner();
        left.pan.value = -spread;
        right.pan.value = spread;
        return { left, right };
    }
}
export const SpatialAudioEngine = new SpatialAudioEngineSingleton();
