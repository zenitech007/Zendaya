import { useShallow } from "zustand/react/shallow";
import { useZendaya, type AiState } from "../store/zendayaStore";

// Encapsulates everything a voice-aware component needs: the live audio
// level, whether the mic/speaker pipeline is active, and small derived
// booleans. Centralizes the "is the voice UI visible right now?" rule
// so each component doesn't repeat the same boolean.
export interface VoiceState {
  ai: AiState;
  audioLevel: number;
  isListening: boolean;
  isSpeaking: boolean;
  isActive: boolean;       // any voice-related state on screen
  voiceActive: boolean;    // user flag from /action activate_voice
  setVoiceActive: (b: boolean) => void;
}

export function useVoiceState(): VoiceState {
  const { ai, audioLevel, voiceActive, setVoiceActive } = useZendaya(
    useShallow((s) => ({
      ai: s.ai,
      audioLevel: s.audioLevel,
      voiceActive: s.voiceActive,
      setVoiceActive: s.setVoiceActive,
    }))
  );

  const isListening = ai === "listening";
  const isSpeaking = ai === "speaking";
  const isActive = voiceActive || isListening || isSpeaking;

  return {
    ai,
    audioLevel,
    isListening,
    isSpeaking,
    isActive,
    voiceActive,
    setVoiceActive,
  };
}
