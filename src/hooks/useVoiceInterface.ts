// hooks/useVoiceInterface.ts
import { useEffect, useRef } from "react";
import { useChatStore } from "../hooks/useChatStore";

export const useVoiceInterface = () => {
  // select only what we need (stable selectors)
  const sessionId = useChatStore((s) => s.sessionId);
  const connectVoice = useChatStore((s) => s.connectVoice);
  const disconnectVoice = useChatStore((s) => s.disconnectVoice);

  const mountedRef = useRef(false);
  const lastSessionRef = useRef<string | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    // session started
    if (sessionId && lastSessionRef.current !== sessionId) {
      console.log("[VoiceInterface] session changed -> connect", sessionId);
      lastSessionRef.current = sessionId;
      connectVoice();
    }

    // session ended
    if (!sessionId && lastSessionRef.current) {
      console.log("[VoiceInterface] session removed -> disconnect");
      lastSessionRef.current = null;
      disconnectVoice();
    }

    return () => {
      // cleanup when the component unmounts
      if (!mountedRef.current) {
        disconnectVoice();
      }
    };
    // intentionally depend only on sessionId (connect/disconnect are stable in store)
  }, [sessionId, connectVoice, disconnectVoice]);
};
