import React, { useEffect, useRef, useState } from "react";
import Lottie from "lottie-react";
import hologramAnim from "../assets/hologram.json";

const Hologram: React.FC = () => {
  const [intensity, setIntensity] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const wsBase = (import.meta.env.VITE_WS_BACKEND_URL || "ws://127.0.0.1:8000").replace(/\/$/, "");
    wsRef.current = new WebSocket(`${wsBase}/ws/hologram`);
    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.event === "hologram_pulse") {
        setIntensity(data.intensity);
      }
    };

    return () => {
      wsRef.current?.close();
    };
  }, []);

  const scale = 1 + Math.min(intensity / 100, 0.5);
  const glow = `0 0 ${Math.min(intensity, 30)}px rgba(0,255,255,0.7)`;

  return (
    <div
      className="fixed bottom-10 right-10 p-4 flex flex-col items-center justify-center"
      style={{
        transform: `scale(${scale})`,
        transition: "transform 0.05s ease",
        filter: `drop-shadow(${glow})`,
      }}
    >
      <Lottie animationData={hologramAnim} loop autoplay style={{ width: 200, height: 200 }} />
      <p className="text-cyan-300 font-semibold mt-2 tracking-widest">ZENDAYA</p>
    </div>
  );
};

export default Hologram;
