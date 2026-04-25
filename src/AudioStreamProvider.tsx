// src/AudioStreamProvider.tsx
"use client";

import React, { createContext, useContext, useEffect, useRef, useState } from "react";

type AudioCtxShape = {
  analyser: AnalyserNode | null;
  isMicActive: boolean;
  isSpeaking: boolean;
  startMic: () => Promise<void>;
  stopMic: () => void;
  playTTS: (text: string) => Promise<void>;
  audioContextReady: boolean;
};

const AudioStreamContext = createContext<AudioCtxShape | undefined>(undefined);

export const useAudioStream = () => {
  const ctx = useContext(AudioStreamContext);
  if (!ctx) throw new Error("useAudioStream must be used within AudioStreamProvider");
  return ctx;
};

export const AudioStreamProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const audioCtxRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | MediaElementAudioSourceNode | null>(null);
  const ttsSourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const [isMicActive, setIsMicActive] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [audioContextReady, setAudioContextReady] = useState(false);

  // Ensure AudioContext exists when first needed
  const ensureAudioContext = () => {
    if (!audioCtxRef.current) {
      const AC = (window.AudioContext || (window as any).webkitAudioContext) as typeof AudioContext;
      audioCtxRef.current = new AC();
      setAudioContextReady(true);
    }
  };

  const createAnalyser = (ctx: AudioContext) => {
    const analy = ctx.createAnalyser();
    analy.fftSize = 2048;
    analy.smoothingTimeConstant = 0.8;
    analyserRef.current = analy;
    return analy;
  };

  const startMic = async () => {
    try {
      ensureAudioContext();
      const ctx = audioCtxRef.current!;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      const src = ctx.createMediaStreamSource(stream);
      sourceRef.current = src;
      const analy = analyserRef.current ?? createAnalyser(ctx);
      // connect src -> analyser but not to destination (no feedback)
      src.connect(analy);
      setIsMicActive(true);
    } catch (err) {
      console.error("startMic error:", err);
      setIsMicActive(false);
    }
  };

  const stopMic = () => {
    try {
      mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
      if (sourceRef.current) {
        try { sourceRef.current.disconnect(); } catch {}
        sourceRef.current = null;
      }
      analyserRef.current = null;
      setIsMicActive(false);
    } catch (err) {
      console.error("stopMic error:", err);
    }
  };

  // Play TTS via backend endpoint; route through analyser so visuals sync
  const playTTS = async (text: string) => {
    try {
      ensureAudioContext();
      setIsSpeaking(true);
      const ctx = audioCtxRef.current!;
      // replace this URL with your TTS endpoint that returns audio blob
      const res = await fetch("http://127.0.0.1:8000/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error("TTS fetch failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.crossOrigin = "anonymous";
      // create media element source and analyser pipeline
      const src = ctx.createMediaElementSource(audio);
      // disconnect previous tts source if exists
      try { ttsSourceRef.current?.disconnect(); } catch {}
      ttsSourceRef.current = src;
      const analy = analyserRef.current ?? createAnalyser(ctx);
      src.connect(analy);
      analy.connect(ctx.destination);
      audio.play().catch((e) => console.error("audio.play() error", e));
      audio.onended = () => {
        try {
          src.disconnect();
          analy.disconnect();
        } catch {}
        ttsSourceRef.current = null;
        setIsSpeaking(false);
        // if mic still active, recreate mic analyser path so visuals keep working
        if (mediaStreamRef.current) {
          const micSrc = ctx.createMediaStreamSource(mediaStreamRef.current);
          const micAnaly = analyserRef.current ?? createAnalyser(ctx);
          try { micSrc.connect(micAnaly); } catch {}
          // don't connect micAnaly to destination
        } else {
          analyserRef.current = null;
        }
      };
    } catch (err) {
      console.error("playTTS error:", err);
      setIsSpeaking(false);
    }
  };

  // Clean up on unload
  useEffect(() => {
    return () => {
      try {
        stopMic();
        if (audioCtxRef.current) {
          audioCtxRef.current.close().catch(() => {});
          audioCtxRef.current = null;
        }
      } catch {}
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value: AudioCtxShape = {
    analyser: analyserRef.current,
    isMicActive,
    isSpeaking,
    startMic,
    stopMic,
    playTTS,
    audioContextReady,
  };

  return <AudioStreamContext.Provider value={value}>{children}</AudioStreamContext.Provider>;
};
