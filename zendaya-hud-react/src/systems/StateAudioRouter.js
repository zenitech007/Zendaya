/**
 * StateAudioRouter.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Translates AiState + action events into audio layer behaviours.
 *
 * Spec mapping:
 *   idle       → calm ambient hum, soft orb pulse
 *   listening  → focused pulse, pitch rises, sonar texture, wider stereo
 *   thinking   → denser modulation, scan textures, particle sounds active
 *   speaking   → warm resonance, ambient ducked, voice FX active
 *   error      → distorted instability, tension layers
 *
 * Also handles action-based events:
 *   open_map   → expansion sweep
 *   dock_orb   → magnetic glide
 *   notification → intelligent ping
 *   warning    → alert resonance
 * ─────────────────────────────────────────────────────────────────────────────
 */
import { AudioManager } from "./AudioManager";
import { SynthEngine } from "./SynthEngine";
const STATE_PROFILES = {
    idle: {
        ambientGain: 0.28,
        orbGain: 0.38,
        intelligenceGain: 0,
        particlesActive: false,
        stereoWidth: 0.12,
    },
    listening: {
        ambientGain: 0.22,
        orbGain: 0.52,
        intelligenceGain: 0.12,
        particlesActive: false,
        stereoWidth: 0.30,
    },
    thinking: {
        ambientGain: 0.35,
        orbGain: 0.48,
        intelligenceGain: 0.55,
        particlesActive: true,
        stereoWidth: 0.20,
    },
    speaking: {
        ambientGain: 0.14, // ducked — voice takes focus (spec §9)
        orbGain: 0.60,
        intelligenceGain: 0,
        particlesActive: false,
        stereoWidth: 0.08,
    },
    error: {
        ambientGain: 0.40,
        orbGain: 0.30,
        intelligenceGain: 0,
        particlesActive: false,
        stereoWidth: 0.05,
    },
    aware: {
        ambientGain: 0.28,
        orbGain: 0.42,
        intelligenceGain: 0.05,
        particlesActive: false,
        stereoWidth: 0.15,
    },
    searching: {
        ambientGain: 0.30,
        orbGain: 0.45,
        intelligenceGain: 0.40,
        particlesActive: true,
        stereoWidth: 0.25,
    },
    mapping: {
        ambientGain: 0.32,
        orbGain: 0.45,
        intelligenceGain: 0.50,
        particlesActive: true,
        stereoWidth: 0.20,
    },
    alert: {
        ambientGain: 0.38,
        orbGain: 0.50,
        intelligenceGain: 0.10,
        particlesActive: false,
        stereoWidth: 0.10,
    },
};
class StateAudioRouterSingleton {
    currentState = null;
    prevState = null;
    // ── Primary state transition handler ─────────────────────────────────────
    onStateChange(next) {
        if (next === this.currentState)
            return;
        this.prevState = this.currentState;
        this.currentState = next;
        this._applyProfile(next);
        this._triggerTransitionSFX(this.prevState, next);
    }
    // ── Action event handler (from WebSocket dispatchAction) ─────────────────
    onAction(action) {
        switch (action) {
            case "open_map":
                SynthEngine.playTransitionSweep("expand");
                AudioManager.setLayerGain("ambient", 0.45); // intensify during map
                break;
            case "close_map":
                SynthEngine.playTransitionSweep("contract");
                AudioManager.resetLayerGain("ambient");
                break;
            case "dock_orb":
                SynthEngine.playDockSound();
                break;
            case "undock_orb":
                SynthEngine.playUndockSound();
                break;
            case "show_notification":
                SynthEngine.playNotificationPing();
                break;
            case "show_terminal":
                SynthEngine.playInteraction("open");
                break;
            case "hide_terminal":
                SynthEngine.playInteraction("close");
                break;
            case "activate_voice":
                SynthEngine.playInteraction("open");
                break;
            case "deactivate_voice":
                SynthEngine.playInteraction("close");
                break;
            case "minimize_ui":
                SynthEngine.playTransitionSweep("minimize");
                break;
            case "restore_ui":
                SynthEngine.playTransitionSweep("restore");
                break;
        }
    }
    // ── WebSocket event handler (spec §14) ───────────────────────────────────
    onWsEvent(event) {
        switch (event) {
            case "assistant_listening":
                this.onStateChange("listening");
                break;
            case "assistant_thinking":
                this.onStateChange("thinking");
                break;
            case "assistant_speaking":
                this.onStateChange("speaking");
                break;
            case "open_map":
                this.onAction("open_map");
                break;
            case "notification":
                SynthEngine.playNotificationPing();
                break;
            case "warning":
                SynthEngine.playAlert("warning");
                break;
        }
    }
    // ── Private helpers ───────────────────────────────────────────────────────
    _applyProfile(state) {
        const p = STATE_PROFILES[state];
        AudioManager.setLayerGain("ambient", p.ambientGain);
        AudioManager.setLayerGain("orb", p.orbGain);
        AudioManager.setLayerGain("intelligence", p.intelligenceGain);
    }
    _triggerTransitionSFX(from, to) {
        // State-entry sounds
        switch (to) {
            case "listening":
                SynthEngine.playOrbState("listening");
                break;
            case "thinking":
                SynthEngine.playOrbState("thinking");
                break;
            case "speaking":
                SynthEngine.playOrbState("speaking");
                // Sidechain: duck ambient while speaking (spec §9)
                AudioManager.duckLayer("ambient", 0.10, 8000, 300);
                AudioManager.duckLayer("orb", 0.28, 8000, 300);
                break;
            case "idle":
                if (from === "thinking" || from === "speaking") {
                    // Resolution tone — subconscious satisfaction (spec §7)
                    SynthEngine.playSuccessResolution();
                }
                SynthEngine.playOrbState("idle");
                break;
            case "error":
                SynthEngine.playAlert("error");
                break;
        }
    }
    getCurrentProfile() {
        return this.currentState ? STATE_PROFILES[this.currentState] : null;
    }
}
export const StateAudioRouter = new StateAudioRouterSingleton();
