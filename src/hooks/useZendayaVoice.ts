// useZendayaVoice.ts
import { useEffect, useRef, useState } from "react";

export function useZendayaVoice(sessionId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationRef = useRef<number | null>(null);

  const [isListening, setIsListening] = useState(false);
  const [volume, setVolume] = useState(0);
  const [connected, setConnected] = useState(false);

  const connectWebSocket = () => {
    if (!sessionId) return;
    const ws = new WebSocket(`ws://localhost:8000/ws/voice?session_id=${sessionId}`);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = (e) => console.error("Zendaya Voice WS error:", e);

    ws.onmessage = async (event) => {
      const audioCtx = audioCtxRef.current ?? new AudioContext();
      audioCtxRef.current = audioCtx;
      const arrayBuffer = event.data instanceof Blob ? await event.data.arrayBuffer() : event.data;
      try {
        const buffer = await audioCtx.decodeAudioData(arrayBuffer.slice(0));
        const src = audioCtx.createBufferSource();
        src.buffer = buffer;
        src.connect(audioCtx.destination);
        src.start();
      } catch (err) {
        console.error("Audio decode failed:", err);
      }
    };
  };

  useEffect(() => {
    connectWebSocket();
    return () => wsRef.current?.close();
  }, [sessionId]);

  const startListening = async () => {
    if (isListening) return;
    setIsListening(true);

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaStreamRef.current = stream;

    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
    audioCtxRef.current = ctx;

    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    analyserRef.current = analyser;
    source.connect(analyser);

    const ws = wsRef.current;
    const processor = ctx.createScriptProcessor(512, 1, 1);
    source.connect(processor);
    processor.connect(ctx.destination);

    processor.onaudioprocess = (e) => {
      const input = e.inputBuffer.getChannelData(0);
      if (ws?.readyState === WebSocket.OPEN) ws.send(input.buffer);
    };

    // Amplitude animation loop
    const dataArray = new Float32Array(analyser.frequencyBinCount);
    const animate = () => {
      analyser.getFloatTimeDomainData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) sum += dataArray[i] * dataArray[i];
      setVolume(Math.sqrt(sum / dataArray.length));
      animationRef.current = requestAnimationFrame(animate);
    };
    animate();
  };

  const stopListening = () => {
    setIsListening(false);
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    animationRef.current && cancelAnimationFrame(animationRef.current);
    if (audioCtxRef.current?.state !== "closed") audioCtxRef.current?.close();
  };

  return { isListening, connected, volume, startListening, stopListening };
}
