import { useEffect, useRef, useState } from "react";
import Lottie from "lottie-react";
import orbAnim from "../assets/hologram_orb.json";

export default function HologramOrb() {
  const [amp, setAmp] = useState(0);
  const wsRef = useRef<WebSocket>();

  useEffect(() => {
    const wsBase = (import.meta.env.VITE_WS_BACKEND_URL || "ws://127.0.0.1:8000").replace(/\/$/, "");
    wsRef.current = new WebSocket(`${wsBase}/ws/hologram`);
    wsRef.current.onmessage = (msg) => {
      const data = JSON.parse(msg.data);
      if (data.type === "amplitude") setAmp(data.amplitude);
    };
    return () => wsRef.current?.close();
  }, []);

  return (
    <div className="fixed bottom-4 right-4 w-64 h-64">
      <Lottie animationData={orbAnim} style={{ opacity: 0.7, transform: `scale(${1 + amp * 0.3})` }}/>
    </div>
  );
}
