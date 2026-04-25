// src/hooks/useWakeWord.ts
import { useEffect, useRef } from "react";
import { useChatStore } from "./useChatStore";
import { isWakeIntent } from "@/utils/isWakeIntent";
import { inferLocalWake } from "@/utils/localWakeModel";
import { emotionBias } from "@/utils/emotionBias";
import { SMART_WAKE_PHRASES } from "@/lib/smartWakePhrases";

export function useWakeWord(enable: boolean, opts = { remoteFallback: true, remoteUrl: "/score-wake", localThreshold: 0.72, remoteThreshold: 0.75 }) {
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const cooldownRef = useRef(false);
  const restartingRef = useRef(false);

  const startListening = useChatStore((s) => s.startListening);
  const isListening = useChatStore((s) => s.isListening);

  useEffect(() => {
    if (!enable) return;
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { console.warn("[WakeWord] SpeechRecognition not available"); return; }

    const rec = new SR();
    rec.continuous = true;
    rec.lang = "en-US";
    rec.interimResults = true;

    rec.onresult = async (e) => {
      const result = e.results[e.results.length - 1];
      if (!result?.[0]) return;
      const text = result[0].transcript.toLowerCase().trim();
      if (text.length < 2) return;

      // Quick phrase list match (explicit phrases)
      if (!cooldownRef.current && !isListening) {
        const heard = text.trim().toLowerCase();
        if (SMART_WAKE_PHRASES.some((p) => heard.includes(p))) {
          cooldownRef.current = true;
          startListening();
          setTimeout(() => (cooldownRef.current = false), 1500);
          return;
        }
      }

      // Heuristic quick accept
      if (isWakeIntent(text) && !cooldownRef.current && !isListening) {
        cooldownRef.current = true;
        startListening();
        setTimeout(() => (cooldownRef.current = false), 1500);
        return;
      }

      // Local model
      try {
        const local = await inferLocalWake(text);
        if (local && local.score >= opts.localThreshold && !cooldownRef.current && !isListening) {
          const finalScore = Math.min(1, local.score + (emotionBias(text) || 0));
          if (finalScore >= opts.localThreshold) {
            cooldownRef.current = true;
            startListening();
            setTimeout(() => (cooldownRef.current = false), 1500);
            return;
          }
        }
      } catch (err) {
        console.warn("[WakeWord] local model error", err);
      }

      // Remote fallback if configured and uncertainty
      if (opts.remoteFallback && !cooldownRef.current && !isListening) {
        try {
          const resp = await fetch(opts.remoteUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ transcript: text }),
          });
          const json = await resp.json();
          const remoteScore = json.score || 0;
          const finalScore = Math.min(1, remoteScore + (emotionBias(text) || 0));
          if (finalScore >= opts.remoteThreshold) {
            cooldownRef.current = true;
            startListening();
            setTimeout(() => (cooldownRef.current = false), 1500);
            return;
          }
        } catch (err) {
          console.warn("[WakeWord] remote scoring failed", err);
        }
      }
    };

    rec.onend = () => {
      if (!isListening && !restartingRef.current) {
        restartingRef.current = true;
        setTimeout(() => {
          restartingRef.current = false;
          try { rec.start(); } catch (err) { console.warn("[WakeWord] restart failed", err); }
        }, 600);
      }
    };

    try { rec.start(); recognitionRef.current = rec; } catch (err) { console.warn("[WakeWord] start failed", err); }

    return () => {
      try { rec.stop(); } catch {}
      recognitionRef.current = null;
    };
  }, [enable, isListening, startListening, opts.localThreshold, opts.remoteFallback, opts.remoteUrl, opts.remoteThreshold]);
}
