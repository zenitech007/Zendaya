/**
 * AdaptiveAudioController.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Spec §12 — Adaptive Audio Engine
 *
 * Listens to store.fps (already measured by useAdaptiveQuality hook)
 * and adjusts the audio layer complexity accordingly:
 *
 *  FPS ≥ 120  → Full spatial layers, all DSP enabled
 *  FPS 60-119 → Standard (defaults)
 *  FPS 45-59  → Reduce particle & intelligence sounds
 *  FPS < 45   → Simplify ambience, disable music
 *
 * Designed to subscribe to the Zustand store externally — call
 * AdaptiveAudioController.start() once after AudioManager.start().
 * ─────────────────────────────────────────────────────────────────────────────
 */
import { AudioManager } from "./AudioManager";
import { AmbientEngine } from "./AmbientEngine";
function fpsTier(fps) {
    if (fps >= 120)
        return "ultra";
    if (fps >= 60)
        return "standard";
    if (fps >= 45)
        return "reduced";
    return "minimal";
}
class AdaptiveAudioControllerSingleton {
    currentTier = "standard";
    unsubscribe = null;
    start() {
        // Lazily import store to avoid circular deps at module load time
        import("../store/zendayaStore").then(({ useZendaya }) => {
            this.unsubscribe = useZendaya.subscribe((state) => {
                this._onFpsChange(state.fps);
            });
        });
    }
    stop() {
        this.unsubscribe?.();
        this.unsubscribe = null;
    }
    _onFpsChange(fps) {
        const tier = fpsTier(fps);
        if (tier === this.currentTier)
            return;
        this.currentTier = tier;
        this._applyTier(tier);
    }
    _applyTier(tier) {
        switch (tier) {
            case "ultra":
                // Full everything — spatial, music, particles
                AudioManager.setLayerGain("ambient", 0.28);
                AudioManager.setLayerGain("orb", 0.45);
                AudioManager.setLayerGain("intelligence", 0.38);
                AudioManager.setLayerGain("music", 0.18);
                AmbientEngine.setComplexity("full");
                break;
            case "standard":
                // Spec defaults — no changes needed
                AudioManager.resetLayerGain("ambient");
                AudioManager.resetLayerGain("orb");
                AudioManager.resetLayerGain("intelligence");
                AudioManager.resetLayerGain("music");
                AmbientEngine.setComplexity("standard");
                break;
            case "reduced":
                // Reduce particle / intelligence sounds (spec §12: "45-60 → reduce particle sounds")
                AudioManager.setLayerGain("intelligence", 0.15);
                AudioManager.setLayerGain("music", 0.08);
                AmbientEngine.setComplexity("reduced");
                break;
            case "minimal":
                // Simplify ambience, disable music (spec §12: "<45 → simplify ambience")
                AudioManager.setLayerGain("ambient", 0.14);
                AudioManager.setLayerGain("intelligence", 0);
                AudioManager.setLayerGain("music", 0);
                AudioManager.setLayerGain("orb", 0.30);
                AmbientEngine.setComplexity("minimal");
                break;
        }
    }
    getCurrentTier() { return this.currentTier; }
}
export const AdaptiveAudioController = new AdaptiveAudioControllerSingleton();
