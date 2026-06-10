import { useEffect, useMemo, useRef } from "react";
import { useFrame, useLoader } from "@react-three/fiber";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import {
  VRM,
  VRMLoaderPlugin,
  VRMUtils,
} from "@pixiv/three-vrm";
import type { AiState, BodyAction } from "../lib/api";
import {
  useBodyAction,
  useFaceRef,
  useMouthRef,
  useVisemeRef,
} from "../hooks/useAiStatus";

export const VRM_URL = "/Zendaya.vrm";

interface Props {
  state: AiState;
}

// VRM rigs vary in expression naming. We try preset names first, then a
// few common author-defined fallbacks. The VRM 1.0 spec uses lowercase
// "aa" / "blink" / "sad"; older 0.x rigs sometimes use "A" / "Blink_L".
const MOUTH_NAMES   = ["aa", "a", "A", "Mouth_A", "Fcl_MTH_A"];
const VISEME_AA     = ["aa", "a", "A", "Mouth_A"];
const VISEME_IH     = ["ih", "i", "I", "Mouth_I"];
const VISEME_EE     = ["ee", "e", "E", "Mouth_E"];
const VISEME_OH     = ["oh", "o", "O", "Mouth_O"];
const VISEME_OU     = ["ou", "u", "U", "Mouth_U"];
const BLINK_NAMES   = ["blink", "Blink", "blink_l", "Blink_L", "Fcl_EYE_Close"];
const SAD_NAMES     = ["sad", "Sad", "sorrow", "Sorrow"];
const HAPPY_NAMES   = ["happy", "Happy", "joy", "Joy", "fun", "Fun"];

function setExpression(vrm: VRM, candidates: string[], value: number): boolean {
  const em = vrm.expressionManager;
  if (!em) return false;
  for (const name of candidates) {
    if (em.getExpression(name)) {
      em.setValue(name, value);
      return true;
    }
  }
  return false;
}

interface BodyClock {
  action: BodyAction["action"];
  startedAt: number;
  duration: number;
}

export default function Avatar({ state }: Props) {
  // Load with the VRM plugin registered against GLTFLoader.
  const gltf = useLoader(GLTFLoader, VRM_URL, (loader) => {
    (loader as GLTFLoader).register((parser) => new VRMLoaderPlugin(parser));
  });

  const vrm = useMemo<VRM | null>(() => {
    const v = (gltf as unknown as { userData: { vrm?: VRM } }).userData.vrm;
    return v ?? null;
  }, [gltf]);

  // Per-state animation clocks
  const stateRef = useRef<AiState>(state);
  stateRef.current = state;

  const tRef = useRef(0);
  const blinkClock = useRef({ t: 0, next: 3.5, phase: 0, blinking: false });

  // Live data refs (no React re-renders for 30Hz signals)
  const mouthRef = useMouthRef();
  const visemeRef = useVisemeRef();
  const faceRef = useFaceRef();
  const mouthSmoothed = useRef(0);
  const gazeX = useRef(0);
  const gazeY = useRef(0);

  // Body language — fires once per ts change.
  const body = useBodyAction();
  const bodyClock = useRef<BodyClock>({ action: "", startedAt: 0, duration: 0 });
  useEffect(() => {
    if (!body.action) return;
    const dur = body.action === "wave" ? 1.4 : 1.0;
    bodyClock.current = {
      action: body.action,
      startedAt: tRef.current,
      duration: dur,
    };
  }, [body.action, body.ts]);

  useEffect(() => {
    if (!vrm) return;
    VRMUtils.removeUnnecessaryVertices(vrm.scene);
    VRMUtils.combineSkeletons(vrm.scene);
    vrm.scene.rotation.y = Math.PI;
    vrm.scene.traverse((obj) => {
      // @ts-expect-error: frustumCulled exists on Object3D
      obj.frustumCulled = false;
    });
  }, [vrm]);

  useFrame((_, delta) => {
    if (!vrm) return;
    tRef.current += delta;
    const t = tRef.current;
    const cur = stateRef.current;

    // ── Always-on: idle blink loop ────────────────────────────
    const bc = blinkClock.current;
    bc.t += delta;
    if (!bc.blinking && bc.t >= bc.next) {
      bc.blinking = true;
      bc.phase = 0;
    }
    if (bc.blinking) {
      bc.phase += delta * 8.0;
      const v = Math.sin(Math.min(bc.phase, Math.PI));
      setExpression(vrm, BLINK_NAMES, Math.max(0, v));
      if (bc.phase >= Math.PI) {
        bc.blinking = false;
        bc.t = 0;
        bc.next = 3.0 + Math.random() * 3.5;
        setExpression(vrm, BLINK_NAMES, 0);
      }
    }

    // ── Gaze: smooth toward the user's face position ──────────
    // Camera +x is to the user's right (we mirror in the perception loop),
    // so a positive face.x means the user is on Zendaya's right; she should
    // turn her head right (positive yaw in VRM convention after the 180°
    // base rotation).
    const face = faceRef.current;
    if (face.present) {
      gazeX.current += (face.x - gazeX.current) * 0.12;
      gazeY.current += (face.y - gazeY.current) * 0.12;
    } else {
      gazeX.current *= 0.95;
      gazeY.current *= 0.95;
    }
    const yawGaze = -gazeX.current * 0.45;       // up to ~26° to a side
    const pitchGaze = gazeY.current * 0.30;       // up to ~17° up/down

    // ── State-driven layers ───────────────────────────────────
    const head = vrm.humanoid?.getNormalizedBoneNode("head");

    if (cur === "talking") {
      // Drive amplitude (jaw open) and per-viseme mouth shape together.
      const targetAmp = mouthRef.current;
      mouthSmoothed.current += (targetAmp - mouthSmoothed.current) * 0.4;
      const live = mouthSmoothed.current;

      const w = visemeRef.current;
      // If any viseme has weight, drive each blendshape; otherwise fall
      // back to the amplitude-driven jaw open.
      const visemeSum = w.aa + w.ih + w.ee + w.oh + w.ou;
      if (visemeSum > 0.01) {
        setExpression(vrm, VISEME_AA, Math.min(1, w.aa * 1.4));
        setExpression(vrm, VISEME_IH, Math.min(1, w.ih * 1.4));
        setExpression(vrm, VISEME_EE, Math.min(1, w.ee * 1.4));
        setExpression(vrm, VISEME_OH, Math.min(1, w.oh * 1.4));
        setExpression(vrm, VISEME_OU, Math.min(1, w.ou * 1.4));
      } else {
        const mouth =
          live > 0.01
            ? Math.min(1.0, live * 1.4)
            : (Math.sin(t * 12) * 0.5 + 0.5) * 0.5;
        setExpression(vrm, MOUTH_NAMES, mouth);
      }
      setExpression(vrm, HAPPY_NAMES, 0.35);
      setExpression(vrm, SAD_NAMES, 0);
      if (head) {
        head.rotation.x = Math.sin(t * 3.2) * 0.04 + pitchGaze;
        head.rotation.y = Math.PI + Math.sin(t * 1.4) * 0.06 + yawGaze;
        head.rotation.z = 0;
      }
    } else if (cur === "thinking") {
      setExpression(vrm, VISEME_AA, 0);
      setExpression(vrm, VISEME_IH, 0);
      setExpression(vrm, VISEME_EE, 0);
      setExpression(vrm, VISEME_OH, 0);
      setExpression(vrm, VISEME_OU, 0);
      setExpression(vrm, MOUTH_NAMES, 0);
      setExpression(vrm, SAD_NAMES, 0.4);
      setExpression(vrm, HAPPY_NAMES, 0);
      if (head) {
        head.rotation.x = -0.05 + pitchGaze * 0.5;
        head.rotation.y = Math.PI + Math.sin(t * 0.5) * 0.05 - 0.10 + yawGaze * 0.5;
        head.rotation.z = -0.18;
      }
    } else {
      setExpression(vrm, VISEME_AA, 0);
      setExpression(vrm, VISEME_IH, 0);
      setExpression(vrm, VISEME_EE, 0);
      setExpression(vrm, VISEME_OH, 0);
      setExpression(vrm, VISEME_OU, 0);
      setExpression(vrm, MOUTH_NAMES, 0);
      setExpression(vrm, SAD_NAMES, 0);
      setExpression(vrm, HAPPY_NAMES, 0.18);
      if (head) {
        head.rotation.x = Math.sin(t * 1.1) * 0.03 + pitchGaze;
        head.rotation.y = Math.PI + Math.sin(t * 0.8) * 0.06 + yawGaze;
        head.rotation.z = 0;
      }
    }

    // ── Body language overlay (nod / shake / wave / shrug) ────
    const clk = bodyClock.current;
    if (clk.action) {
      const elapsed = t - clk.startedAt;
      if (elapsed > clk.duration) {
        clk.action = "";
      } else {
        const phase = (elapsed / clk.duration) * Math.PI * 2;
        const damp = 1.0 - elapsed / clk.duration;
        if (head) {
          if (clk.action === "nod") {
            head.rotation.x += Math.sin(phase * 2) * 0.35 * damp;
          } else if (clk.action === "shake") {
            head.rotation.y += Math.sin(phase * 2) * 0.30 * damp;
          } else if (clk.action === "shrug") {
            head.rotation.x += -0.15 * damp;
          } else if (clk.action === "wave") {
            head.rotation.z += Math.sin(phase * 1.5) * 0.10 * damp;
          }
        }
        // Wave: try to actually raise the right arm if the rig has it.
        if (clk.action === "wave") {
          const rUpper = vrm.humanoid?.getNormalizedBoneNode("rightUpperArm");
          const rLower = vrm.humanoid?.getNormalizedBoneNode("rightLowerArm");
          if (rUpper) {
            rUpper.rotation.z = -1.5 * damp; // arm out to the side
            rUpper.rotation.x = -0.2 * damp;
          }
          if (rLower) {
            rLower.rotation.y = Math.sin(phase * 4) * 0.6 * damp;
          }
        }
      }
    }

    vrm.update(delta);
  });

  if (!vrm) return null;
  return <primitive object={vrm.scene} />;
}
