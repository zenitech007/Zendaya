import { useShallow } from "zustand/react/shallow";
import { useZendaya } from "../store/zendayaStore";
export function useVoiceState() {
    const { ai, audioLevel, voiceActive, setVoiceActive } = useZendaya(useShallow((s) => ({
        ai: s.ai,
        audioLevel: s.audioLevel,
        voiceActive: s.voiceActive,
        setVoiceActive: s.setVoiceActive,
    })));
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
