/**
 * useVoicePlayback.ts — resume the voice AudioContext on first user gesture.
 *
 * Mount once at the App root. Browsers keep a freshly created AudioContext
 * suspended until the user interacts; this hook calls voicePlayer.unlock()
 * on the first click/keydown/touch, then detaches. Playback itself is driven
 * by useWebSocket → voicePlayer.handle().
 */
import { useEffect } from "react";
import { voicePlayer } from "../audio/voicePlayer";

export function useVoicePlayback(): void {
  useEffect(() => {
    let unlocked = false;
    const onGesture = () => {
      if (unlocked) return;
      unlocked = true;
      voicePlayer.unlock();
      window.removeEventListener("click", onGesture);
      window.removeEventListener("keydown", onGesture);
      window.removeEventListener("touchstart", onGesture);
    };
    window.addEventListener("click", onGesture);
    window.addEventListener("keydown", onGesture);
    window.addEventListener("touchstart", onGesture);
    return () => {
      window.removeEventListener("click", onGesture);
      window.removeEventListener("keydown", onGesture);
      window.removeEventListener("touchstart", onGesture);
    };
  }, []);
}
