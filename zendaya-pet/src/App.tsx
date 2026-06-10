import { Suspense, useEffect, useState } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { PerspectiveCamera, OrbitControls } from "@react-three/drei";
import { EffectComposer, Bloom, DepthOfField, ToneMapping } from "@react-three/postprocessing";
import { ToneMappingMode } from "postprocessing";
import Avatar from "./components/Avatar";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { useAiStatus } from "./hooks/useAiStatus";
import { useFaceMode } from "./hooks/useFaceMode";
import { useWindowRoam } from "./hooks/useWindowRoam";

const DEBUG_ORBIT = false;

// Pulled back and lowered to frame the full body. VRM origin is at the
// feet (Y=0); head sits around Y=1.5, so a center near Y=0.85 keeps the
// whole figure inside the viewport with breathing room.
const CAMERA_POSITION: [number, number, number] = [0, 0.85, 3.6];
const CAMERA_TARGET:   [number, number, number] = [0, 0.85, 0];

const AVAILABLE_MODELS = [
  "/Zendaya.vrm",
  "/Zendaya-orange.vrm",
  "/8901823834180444571.vrm"
];

export default function App() {
  const { state, text } = useAiStatus();
  const faceMode = useFaceMode();
  const [modelIdx, setModelIdx] = useState(0);

  // Pause roaming while the pet face is hidden (minimize/hud modes).
  useWindowRoam(faceMode === "pet" || faceMode === "anime");

  const handleRightClick = (e: React.MouseEvent) => {
    e.preventDefault();
    setModelIdx((prev) => (prev + 1) % AVAILABLE_MODELS.length);
  };

  return (
    <ErrorBoundary fallbackTitle="Zendaya Pet UI crashed">
      <div
        data-tauri-drag-region
        onContextMenu={handleRightClick}
        className="w-screen h-screen overflow-hidden relative select-none cursor-default"
        style={{ background: "transparent" }}
      >
        <Canvas
          gl={{ alpha: true, antialias: true, premultipliedAlpha: false }}
          style={{ background: "transparent", pointerEvents: "none" }}
        >
          <PerspectiveCamera
            makeDefault
            position={CAMERA_POSITION}
            fov={32}
            near={0.05}
            far={20}
          />
          {DEBUG_ORBIT ? (
            <OrbitControls target={CAMERA_TARGET} />
          ) : (
            <CameraLookAt target={CAMERA_TARGET} />
          )}

          <ambientLight intensity={0.7} />
          <directionalLight position={[2, 4, 3]} intensity={1.0} />
          <directionalLight position={[-2, 2, -1]} intensity={0.4} />
          <Suspense fallback={null}>
            <Avatar state={state} text={text} modelUrl={AVAILABLE_MODELS[modelIdx]} />
          </Suspense>
          <EffectComposer multisampling={4}>
            <DepthOfField target={[0, 0.85, 0]} focalLength={0.02} bokehScale={2.5} height={480} />
            <Bloom luminanceThreshold={0.8} luminanceSmoothing={0.9} height={300} intensity={1.2} />
            <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
          </EffectComposer>
        </Canvas>
      </div>
    </ErrorBoundary>
  );
}

function CameraLookAt({ target }: { target: [number, number, number] }) {
  const camera = useThree((s) => s.camera);
  useEffect(() => {
    camera.lookAt(target[0], target[1], target[2]);
    camera.updateProjectionMatrix();
  }, [camera, target]);
  return null;
}
