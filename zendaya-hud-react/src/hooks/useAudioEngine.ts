/**
 * useAudioEngine.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Master audio bootstrap hook — mount once at the App root.
 *
 * Responsibilities:
 *  1. Start AudioManager on first user gesture (autoplay policy compliance)
 *  2. Start AmbientEngine (always-on layer §3)
 *  3. Start AdaptiveAudioController (FPS-aware §12)
 *  4. Subscribe to Zustand ai state → StateAudioRouter
 *  5. Subscribe to Zustand action events → StateAudioRouter
 *  6. Expose { muted, setMuted, volume, setVolume }
 *
 * Usage: call useAudioEngine() once in App.tsx — no other setup needed.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { AudioManager } from "../systems/AudioManager";
import { AmbientEngine } from "../systems/AmbientEngine";
import { ambientParamsFor } from "../systems/ambientParams";
import { StateAudioRouter } from "../systems/StateAudioRouter";
import { AdaptiveAudioController } from "../systems/AdaptiveAudioController";
import { SpatialAudioEngine } from "../systems/SpatialAudioEngine";
import { useZendaya } from "../store/zendayaStore";

export function useAudioEngine() {
  const [muted, setMutedState] = useState(false);
  const [volume, setVolumeState] = useState(1.0);
  const bootstrapped = useRef(false);

  // ── Bootstrap on first user interaction ──────────────────────────────────
  useEffect(() => {
    const bootstrap = async () => {
      if (bootstrapped.current) return;
      bootstrapped.current = true;

      AudioManager.start();
      await AudioManager.resume();

      // Kick off ambient layer — slowly fades in (3 s)
      AmbientEngine.start();
      // Shape the ambient synth to the current theme.
      AmbientEngine.applyTheme(ambientParamsFor(useZendaya.getState().activeThemeId));

      // Orb stereo drift
      SpatialAudioEngine.startOrbDrift();

      // FPS-adaptive quality
      AdaptiveAudioController.start();
    };

    // Trigger on first click or keydown — respects browser autoplay policies
    const handleInteraction = () => {
      bootstrap();
      window.removeEventListener("click", handleInteraction);
      window.removeEventListener("keydown", handleInteraction);
      window.removeEventListener("touchstart", handleInteraction);
    };

    window.addEventListener("click", handleInteraction, { once: true });
    window.addEventListener("keydown", handleInteraction, { once: true });
    window.addEventListener("touchstart", handleInteraction, { once: true });

    return () => {
      window.removeEventListener("click", handleInteraction);
      window.removeEventListener("keydown", handleInteraction);
      window.removeEventListener("touchstart", handleInteraction);
    };
  }, []);

  // ── Subscribe to AI state changes ─────────────────────────────────────────
  useEffect(() => {
    let prev = useZendaya.getState().ai;
    const unsub = useZendaya.subscribe((state) => {
      if (state.ai !== prev) {
        StateAudioRouter.onStateChange(state.ai);
        prev = state.ai;
      }
    });
    return () => unsub();
  }, []);

  // ── Subscribe to docked state for dock/undock sounds ─────────────────────
  useEffect(() => {
    let prev = useZendaya.getState().docked;
    const unsub = useZendaya.subscribe((state) => {
      if (state.docked !== prev) {
        StateAudioRouter.onAction(state.docked ? "dock_orb" : "undock_orb");
        prev = state.docked;
      }
    });
    return () => unsub();
  }, []);

  // ── Subscribe to scene changes for transition sweeps ─────────────────────
  useEffect(() => {
    let prev = useZendaya.getState().scene;
    const unsub = useZendaya.subscribe((state) => {
      if (state.scene !== prev) {
        if (state.scene === "map") StateAudioRouter.onAction("open_map");
        else StateAudioRouter.onAction("close_map");
        prev = state.scene;
      }
    });
    return () => unsub();
  }, []);

  // ── Subscribe to terminal open/close ─────────────────────────────────────
  useEffect(() => {
    let prev = useZendaya.getState().terminalOpen;
    const unsub = useZendaya.subscribe((state) => {
      if (state.terminalOpen !== prev) {
        StateAudioRouter.onAction(state.terminalOpen ? "show_terminal" : "hide_terminal");
        prev = state.terminalOpen;
      }
    });
    return () => unsub();
  }, []);

  // ── Subscribe to voice active ─────────────────────────────────────────────
  useEffect(() => {
    let prev = useZendaya.getState().voiceActive;
    const unsub = useZendaya.subscribe((state) => {
      if (state.voiceActive !== prev) {
        StateAudioRouter.onAction(state.voiceActive ? "activate_voice" : "deactivate_voice");
        prev = state.voiceActive;
      }
    });
    return () => unsub();
  }, []);

  // ── Subscribe to minimize ─────────────────────────────────────────────────
  useEffect(() => {
    let prev = useZendaya.getState().minimized;
    const unsub = useZendaya.subscribe((state) => {
      if (state.minimized !== prev) {
        StateAudioRouter.onAction(state.minimized ? "minimize_ui" : "restore_ui");
        prev = state.minimized;
      }
    });
    return () => unsub();
  }, []);

  // ── Subscribe to notifications ────────────────────────────────────────────
  useEffect(() => {
    let prevCount = useZendaya.getState().notifications.length;
    const unsub = useZendaya.subscribe((state) => {
      const count = state.notifications.length;
      if (count > prevCount) {
        StateAudioRouter.onAction("show_notification");
      }
      prevCount = count;
    });
    return () => unsub();
  }, []);

  // ── Subscribe to theme changes → reshape ambient timbre ──────────────────
  useEffect(() => {
    let prev = useZendaya.getState().activeThemeId;
    const unsub = useZendaya.subscribe((state) => {
      if (state.activeThemeId !== prev) {
        AmbientEngine.applyTheme(ambientParamsFor(state.activeThemeId));
        prev = state.activeThemeId;
      }
    });
    return () => unsub();
  }, []);

  // ── Mute / volume controls ────────────────────────────────────────────────
  const setMuted = useCallback((m: boolean) => {
    setMutedState(m);
    AudioManager.setMasterGain(m ? 0 : volume);
  }, [volume]);

  const setVolume = useCallback((v: number) => {
    const clamped = Math.max(0, Math.min(1, v));
    setVolumeState(clamped);
    if (!muted) AudioManager.setMasterGain(clamped);
  }, [muted]);

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      AmbientEngine.stop();
      SpatialAudioEngine.stopOrbDrift();
      AdaptiveAudioController.stop();
      AudioManager.dispose();
    };
  }, []);

  return { muted, setMuted, volume, setVolume };
}
