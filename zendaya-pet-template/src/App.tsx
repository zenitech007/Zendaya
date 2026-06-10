import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import Avatar from "./components/Avatar";
import ChatBox from "./components/ChatBox";
import Hud from "./components/Hud";
import SpeechBubble from "./components/SpeechBubble";
import { useAiStatus } from "./hooks/useAiStatus";
import { useFaceMode } from "./hooks/useFaceMode";

export default function App() {
  const { state, text, connected } = useAiStatus();
  useFaceMode();

  return (
    <div
      data-tauri-drag-region
      className="w-screen h-screen bg-transparent overflow-hidden relative select-none cursor-default"
    >
      <Canvas
        camera={{ position: [0, 1.4, 2.0], fov: 25 }}
        gl={{ alpha: true, antialias: true, premultipliedAlpha: false }}
        style={{ background: "transparent" }}
      >
        <ambientLight intensity={0.7} />
        <directionalLight position={[2, 4, 3]} intensity={1.0} />
        <directionalLight position={[-2, 2, -1]} intensity={0.4} />
        <Suspense fallback={null}>
          <Avatar state={state} />
        </Suspense>
      </Canvas>

      {state === "talking" && text && <SpeechBubble text={text} />}

      <Hud />
      <ChatBox connected={connected} />
    </div>
  );
}
