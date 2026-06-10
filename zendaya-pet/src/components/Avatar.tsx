import { useEffect, useMemo, useRef } from "react";
import { useFrame, useLoader } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import {
  VRM,
  VRMHumanBoneName,
  VRMLoaderPlugin,
  VRMUtils,
} from "@pixiv/three-vrm";
import { invoke } from "@tauri-apps/api/core";
import { getVisemes, type AiState, type VisemeMap } from "../lib/api";
import { PetMovement } from "../hooks/useWindowRoam";

interface WindowInfo {
  title: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export const VRM_URL = "/Zendaya.vrm";

interface Props {
  state: AiState;
  text?: string;
  modelUrl?: string;
}

// VRM 1.0 preset names are lowercase; older 0.x rigs sometimes export the
// author's raw names. Each list is tried in order until one resolves.
const E = {
  AA:    ["aa", "a", "A", "Mouth_A", "Fcl_MTH_A"],
  IH:    ["ih", "i", "I", "Mouth_I", "Fcl_MTH_I"],
  OU:    ["ou", "u", "U", "Mouth_U", "Fcl_MTH_U"],
  EE:    ["ee", "e", "E", "Mouth_E", "Fcl_MTH_E"],
  OH:    ["oh", "o", "O", "Mouth_O", "Fcl_MTH_O"],
  BLINK: ["blink", "Blink", "blink_l", "Blink_L", "Fcl_EYE_Close"],
  HAPPY: ["happy", "Happy", "joy", "Joy", "fun", "Fun"],
  SAD:   ["sad", "Sad", "sorrow", "Sorrow"],
  ANGRY: ["angry", "Angry"],
  SURP:  ["surprised", "Surprised", "Fcl_ALL_Surprised"],
  RELAX: ["relaxed", "Relaxed"],
};

function setExpr(vrm: VRM, candidates: string[], value: number) {
  const em = vrm.expressionManager;
  if (!em) return;
  for (const name of candidates) {
    if (em.getExpression(name)) {
      em.setValue(name, THREE.MathUtils.clamp(value, 0, 1));
      return;
    }
  }
}

const REST_POSE = {
  leftShoulder:  { x: 0.0,  y: 0.0,  z:  0.10 },
  rightShoulder: { x: 0.0,  y: 0.0,  z: -0.10 },
  leftUpperArm:  { x: 0.05, y: 0.0,  z:  1.25 },
  rightUpperArm: { x: 0.05, y: 0.0,  z: -1.25 },
  leftLowerArm:  { x: 0.0,  y: 0.20, z:  0.0 },
  rightLowerArm: { x: 0.0,  y: -0.20, z:  0.0 },
};

// Lightweight sentiment from the latest utterance — feeds emotional pose,
// not lip sync. Returns weights summing to <=1 across happy/sad/angry/surp.
function readSentiment(text: string) {
  const s = text.toLowerCase();
  const happy = /\b(haha|lol|yay|great|love|awesome|nice|cool|thanks|thank you|sweet|perfect|excellent|good)\b/.test(s);
  const sad   = /\b(sorry|sad|unfortunately|miss|hurts?|broken?|fail(ed)?|cry(ing)?)\b/.test(s);
  const angry = /\b(angry|annoyed|frustrated|hate|stupid|damn|wtf)\b/.test(s);
  const surp  = /\b(wow|whoa|oh|really|seriously|huh|what\?+|no way)\b/.test(s) || /[!?]{2,}/.test(text);
  const curious = /\?$/.test(text.trim());
  return {
    happy: happy ? 0.6 : 0,
    sad:   sad   ? 0.55 : 0,
    angry: angry ? 0.5 : 0,
    surp:  surp  ? 0.55 : 0,
    curious: curious ? 0.7 : 0,
  };
}

export default function Avatar({ state, text = "", modelUrl = VRM_URL }: Props) {
  const gltf = useLoader(GLTFLoader, modelUrl, (loader) => {
    (loader as GLTFLoader).register((parser) => new VRMLoaderPlugin(parser));
  });

  const vrm = useMemo<VRM | null>(() => {
    const v = (gltf as unknown as { userData: { vrm?: VRM } }).userData.vrm;
    return v ?? null;
  }, [gltf]);

  const restRot = useRef<Record<string, { x: number; y: number; z: number }>>({});

  const stateRef = useRef<AiState>(state);
  stateRef.current = state;

  const tRef = useRef(0);
  const blinkClock = useRef({ t: 0, next: 3.5, phase: 0, blinking: false });

  // Lip-sync clock keyed off the live utterance text. Each character is
  // pronounced for ~70ms; vowels open the mouth, consonants close it.
  const speech = useRef({ text: "", startT: 0, lastIdx: -1 });
  // Reaction pulse triggered when text changes.
  const reaction = useRef({ t0: -10, kind: "none" as "none" | "react" | "surprise" });

  useEffect(() => {
    speech.current.text = text;
    speech.current.startT = tRef.current;
    speech.current.lastIdx = -1;
    if (text && text.trim().length > 0) {
      reaction.current.t0 = tRef.current;
      reaction.current.kind = /[!?]/.test(text) ? "surprise" : "react";
      triggerRespond.current = tRef.current;
    }
  }, [text]);

  // Mouse follow — eyes/head track cursor while idle.
  const mouseRef = useRef({ x: 0, y: 0 });
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      mouseRef.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      mouseRef.current.y = -((e.clientY / window.innerHeight) * 2 - 1);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  const saccade = useRef({
    target: new THREE.Vector3(),
    current: new THREE.Vector3(),
    nextUpdate: 0
  });

  const osContext = useRef<"normal" | "coding" | "music" | "gaming">("normal");
  const liveVisemes = useRef<VisemeMap>({ aa: 0, ih: 0, ee: 0, oh: 0, ou: 0 });

  // Poll live audio viseme data from the Python backend (25Hz)
  useEffect(() => {
    let cancelled = false;
    const fetchV = async () => {
      try {
        const v = await getVisemes();
        if (!cancelled && v) {
          liveVisemes.current = v;
        }
      } catch (err) {}
    };
    
    // 40ms = 25fps lip sync
    const interval = setInterval(fetchV, 40);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    const scanOS = async () => {
      try {
        const windows = await invoke<WindowInfo[]>("get_active_windows");
        if (!windows || windows.length === 0) return;
        
        const topWin = windows[0]; // Usually the focused window is at the top of the Z-order
        const title = topWin.title.toLowerCase();
        
        if (title.includes("code") || title.includes("cursor") || title.includes("studio")) {
          osContext.current = "coding";
        } else if (title.includes("spotify") || title.includes("music") || title.includes("itunes")) {
          osContext.current = "music";
        } else if (title.includes("game") || title.includes("steam") || title.includes("play")) {
          osContext.current = "gaming";
        } else {
          osContext.current = "normal";
        }
      } catch (err) {
        // Ignore errors if Tauri isn't ready
      }
    };
    
    scanOS();
    const interval = setInterval(scanOS, 5000);
    return () => clearInterval(interval);
  }, []);

  // Activity controller — picks behaviors over time so she does more than
  // just walk. The activity owns gait/arm overrides for the frame.
  type Activity =
    | "walk"
    | "idle_look"
    | "wave"
    | "stretch"
    | "dance"
    | "peek"
    | "respond"
    | "look_around"
    | "nod"
    | "cheer"
    | "tap_foot"
    | "bow"
    | "arms_crossed"
    | "ponder"
    | "sit_on_window"
    | "peek_from_screen_edge"
    | "jump";
  const groupRef = useRef<THREE.Group>(null);
  const wander = useRef({
    target: 0,
    speed: 0.22,
    facing: Math.PI,
    targetFacing: Math.PI,
    walkPhase: 0,
    walkAmount: 0,
  });
  const activity = useRef<{
    name: Activity;
    startT: number;
    durS: number;
    pendingNext: number; // time at which activity should be re-rolled
  }>({ name: "idle_look", startT: 0, durS: 4, pendingNext: 4 });

  const triggerRespond = useRef(0); // marker bumped on new utterances

  // Pick a random next activity. Walk most often; sprinkle the rest.
  function rollActivity(): { name: Activity; durS: number } {
    const r = Math.random();
    const ctx = osContext.current;

    // Contextual Overrides
    if (ctx === "coding" && r < 0.40) return { name: "ponder", durS: 4.0 };
    if (ctx === "music"  && r < 0.40) return { name: Math.random() > 0.5 ? "dance" : "tap_foot", durS: 5.0 };
    if (ctx === "gaming" && r < 0.30) return { name: Math.random() > 0.5 ? "cheer" : "jump", durS: 2.4 };

    if (r < 0.28) return { name: "walk",         durS: 4 + Math.random() * 4 };
    if (r < 0.35) return { name: "sit_on_window",durS: 8 + Math.random() * 6 }; // 7% chance
    if (r < 0.40) return { name: "peek_from_screen_edge", durS: 4.5 }; // 5% chance
    if (r < 0.44) return { name: "jump",         durS: 1.5 }; // 4% chance
    if (r < 0.48) return { name: "idle_look",    durS: 2 + Math.random() * 2 };
    if (r < 0.52) return { name: "look_around",  durS: 3.0 };
    if (r < 0.58) return { name: "wave",         durS: 2.4 };
    if (r < 0.66) return { name: "stretch",      durS: 3.0 };
    if (r < 0.74) return { name: "dance",        durS: 5.0 };
    if (r < 0.80) return { name: "peek",         durS: 2.2 };
    if (r < 0.86) return { name: "nod",          durS: 1.8 };
    if (r < 0.90) return { name: "cheer",        durS: 2.4 };
    if (r < 0.94) return { name: "tap_foot",     durS: 3.0 };
    if (r < 0.97) return { name: "bow",          durS: 2.2 };
    if (r < 0.99) return { name: "arms_crossed", durS: 3.5 };
    return                { name: "ponder",      durS: 3.0 };
  }

  useEffect(() => {
    if (!vrm) return;
    VRMUtils.removeUnnecessaryVertices(vrm.scene);
    VRMUtils.combineSkeletons(vrm.scene);
    vrm.scene.traverse((obj) => {
      obj.frustumCulled = false;
    });
    const humanoid = vrm.humanoid;
    if (humanoid) {
      const apply = (
        boneName: VRMHumanBoneName,
        e: { x: number; y: number; z: number },
        key: string
      ) => {
        const node = humanoid.getNormalizedBoneNode(boneName);
        if (!node) return;
        node.rotation.set(e.x, e.y, e.z);
        restRot.current[key] = { x: e.x, y: e.y, z: e.z };
      };
      apply(VRMHumanBoneName.LeftShoulder,  REST_POSE.leftShoulder,  "leftShoulder");
      apply(VRMHumanBoneName.RightShoulder, REST_POSE.rightShoulder, "rightShoulder");
      apply(VRMHumanBoneName.LeftUpperArm,  REST_POSE.leftUpperArm,  "leftUpperArm");
      apply(VRMHumanBoneName.RightUpperArm, REST_POSE.rightUpperArm, "rightUpperArm");
      apply(VRMHumanBoneName.LeftLowerArm,  REST_POSE.leftLowerArm,  "leftLowerArm");
      apply(VRMHumanBoneName.RightLowerArm, REST_POSE.rightLowerArm, "rightLowerArm");
    }
  }, [vrm]);

  const sentiment = useMemo(() => readSentiment(text), [text]);

  useFrame((_, deltaRaw) => {
    if (!vrm) return;
    const delta = Math.min(deltaRaw, 1 / 30); // clamp huge frames
    tRef.current += delta;
    const t = tRef.current;
    const cur = stateRef.current;
    const humanoid = vrm.humanoid;
    if (!humanoid) {
      vrm.update(delta);
      return;
    }

    const get = (b: VRMHumanBoneName) => humanoid.getNormalizedBoneNode(b);

    // ── Blink (faster blink rate when surprised, slower when sad) ──
    const bc = blinkClock.current;
    bc.t += delta;
    if (!bc.blinking && bc.t >= bc.next) {
      bc.blinking = true;
      bc.phase = 0;
    }
    if (bc.blinking) {
      bc.phase += delta * 8.0;
      const v = Math.sin(Math.min(bc.phase, Math.PI));
      setExpr(vrm, E.BLINK, Math.max(0, v));
      if (bc.phase >= Math.PI) {
        bc.blinking = false;
        bc.t = 0;
        const baseNext = sentiment.surp > 0 ? 1.6 : sentiment.sad > 0 ? 5.0 : 3.0;
        bc.next = baseNext + Math.random() * 2.5;
        setExpr(vrm, E.BLINK, 0);
      }
    }

    // ── Breathing (slightly faster when excited) ──
    const breathRate = 1.6 + sentiment.surp * 0.8 + sentiment.angry * 0.6;
    const breath = Math.sin(t * breathRate) * 0.025;
    const chest = get(VRMHumanBoneName.Chest) ?? get(VRMHumanBoneName.UpperChest);
    const spine = get(VRMHumanBoneName.Spine);
    if (chest) chest.rotation.x = -breath * 0.5;
    if (spine) spine.rotation.x = -breath * 0.3;

    // ── Activity controller ──
    // Pick the next behavior when the current one expires. A new utterance
    // forces "respond" (waves and says hi).
    const act = activity.current;
    if (triggerRespond.current > act.startT) {
      act.name = "respond";
      act.startT = t;
      act.durS = 2.4;
      act.pendingNext = t + act.durS;
      // Also park any in-flight walk target.
      wander.current.walkAmount = Math.min(wander.current.walkAmount, 0.5);
    } else if (t >= act.pendingNext) {
      const next = rollActivity();
      act.name = next.name;
      act.startT = t;
      act.durS = next.durS;
      act.pendingNext = t + next.durS;

      // When choosing to sit on a window, immediately fetch the active OS windows
      if (act.name === "sit_on_window") {
        invoke<WindowInfo[]>("get_active_windows")
          .then((windows) => {
            if (windows && windows.length > 0) {
              // Pick a large-ish window to sit on (e.g. Chrome, VS Code)
              const validWindows = windows.filter(w => w.width > 500 && w.height > 400);
              if (validWindows.length > 0) {
                const targetWin = validWindows[Math.floor(Math.random() * validWindows.length)];
                
                // Calculate position to sit on top edge
                // Her window is 420x820. Her feet are near the bottom.
                // To rest her butt on the window, we position the OS window
                // so her feet are slightly below the top edge.
                const sitX = targetWin.x + targetWin.width / 2 - 210; // Center over window
                const sitY = targetWin.y - 780; // Sit on the top edge
                PetMovement.setTarget(sitX, sitY);
              }
            }
          })
          .catch(err => console.warn("Could not fetch windows:", err));
      }
      
      // When choosing to peek from screen edge, set target to the closest monitor edge
      if (act.name === "peek_from_screen_edge") {
        const distToLeft = PetMovement.currentX - PetMovement.minX;
        const distToRight = PetMovement.maxX - PetMovement.currentX;
        const hideX = distToLeft < distToRight ? PetMovement.minX - 180 : PetMovement.maxX + 180;
        PetMovement.setTarget(hideX, PetMovement.maxY); // Hide just off screen
      }

      // If we are exiting a sit, walk, or peek state, gradually return her to the floor (maxY)
      if (act.name !== "sit_on_window" && act.name !== "walk" && act.name !== "peek_from_screen_edge" && !PetMovement.active) {
        PetMovement.setTarget(PetMovement.currentX, PetMovement.maxY);
      }
    }

    const aLocal = t - act.startT;          // seconds into current activity
    const aPhase = aLocal / Math.max(0.01, act.durS); // 0..1 progress

    // Maintain a smoothed pose state to act as an Animation Blending Tree.
    // This prevents any snapping when changing from one activity to another,
    // bringing the animation to a game-engine standard.
    if (!groupRef.current) return;
    if (!groupRef.current.userData.currentPose) {
      groupRef.current.userData.currentPose = {
        walkPower: 0,
        lUpArm:  { x: 0, y: 0, z: 0 }, rUpArm:  { x: 0, y: 0, z: 0 },
        lLoArm:  { x: 0, y: 0, z: 0 }, rLoArm:  { x: 0, y: 0, z: 0 },
        lShoulder: { x: 0, y: 0, z: 0 }, rShoulder: { x: 0, y: 0, z: 0 },
        lUpLeg:  { x: 0, y: 0, z: 0 }, rUpLeg:  { x: 0, y: 0, z: 0 },
        lLoLeg:  { x: 0 }, rLoLeg:  { x: 0 },
        hipsZ: 0, hipsY: 0, spineX: 0, spineZ: 0, facingOffset: 0,
        head: { x: 0, y: 0, z: 0 },
      };
    }
    const currentPose = groupRef.current.userData.currentPose;

    // Pose accumulators — each activity writes into these.
    const pose = {
      walkPower: 0,
      lUpArm:  { x: 0, y: 0, z: 0 }, rUpArm:  { x: 0, y: 0, z: 0 },
      lLoArm:  { x: 0, y: 0, z: 0 }, rLoArm:  { x: 0, y: 0, z: 0 },
      lShoulder: { x: 0, y: 0, z: 0 }, rShoulder: { x: 0, y: 0, z: 0 },
      lUpLeg:  { x: 0, y: 0, z: 0 }, rUpLeg:  { x: 0, y: 0, z: 0 },
      lLoLeg:  { x: 0 }, rLoLeg:  { x: 0 },
      hipsZ: 0, hipsY: 0, spineX: 0, spineZ: 0, facingOffset: 0,
      head: { x: 0, y: 0, z: 0, override: false },
      forceFaceCamera: false,
    };

    const g = groupRef.current;

    if (act.name === "walk") {
      // Walk across the physical monitor!
      // We don't move g.position.x anymore. We set PetMovement target.
      pose.walkPower = 1;
      
      if (!PetMovement.active) {
        // Pick a new random target on the screen
        const minX = PetMovement.minX;
        const maxX = PetMovement.maxX;
        let nextX = Math.floor(minX + Math.random() * (maxX - minX));
        
        // Ensure she walks a decent distance
        if (Math.abs(nextX - PetMovement.currentX) < (maxX - minX) * 0.25) {
          nextX = nextX < (minX + maxX) / 2 ? maxX - 40 : minX + 40;
        }
        
        // We only move horizontally for now, OS y is constant
        PetMovement.setTarget(nextX, PetMovement.currentY);
      }

      // Turn her body towards the direction she's physically moving
      const dx = PetMovement.targetX - PetMovement.currentX;
      if (Math.abs(dx) > 2) {
        const dir = Math.sign(dx);
        // Face left or right in 3D space
        wander.current.targetFacing = Math.PI + dir * 0.45;
      } else {
        wander.current.targetFacing = Math.PI; // Face forward if arrived
      }
    } else {
      pose.forceFaceCamera = true;
      wander.current.targetFacing = Math.PI;
    }

    if (act.name === "idle_look") {
      // Subtle weight shift + occasional glance — handled by head logic.
      pose.hipsZ = Math.sin(t * 0.7) * 0.04;
      pose.spineZ = Math.sin(t * 0.7) * 0.02;
    }

    if (act.name === "wave" || act.name === "respond") {
      // Right arm raises to ~ horizontal, hand waves side-to-side.
      // Cubic ease-in / ease-out so the raise looks intentional.
      const raise = Math.sin(Math.min(1, aLocal / 0.45) * Math.PI / 2) // 0→1 in 0.45s
                  * Math.sin(Math.max(0, 1 - (aLocal - (act.durS - 0.5)) / 0.5) * Math.PI / 2); // hold then lower
      // raise can briefly go negative as we cross hold→lower; clamp
      const raiseClamped = THREE.MathUtils.clamp(raise, 0, 1);
      // Bring upper arm UP and slightly forward. Rest is z=-1.25 (down);
      // we offset by +1.0 toward 0 to lift it.
      pose.rUpArm.z = +1.05 * raiseClamped;
      pose.rUpArm.x = -0.30 * raiseClamped;
      pose.rShoulder.z = -0.25 * raiseClamped;
      // Hand waving — elbow bends and forearm rocks.
      const wave = Math.sin(aLocal * 8) * raiseClamped;
      pose.rLoArm.x = -0.6 * raiseClamped;
      pose.rLoArm.z = wave * 0.5;
      // Lean head/shoulder forward a tad.
      pose.spineX = -0.04 * raiseClamped;
    }

    if (act.name === "stretch") {
      // Both arms reach UP overhead, slight back-arch.
      const lift = Math.sin(THREE.MathUtils.clamp(aPhase, 0, 1) * Math.PI);
      pose.lUpArm.z = -1.40 * lift; // opposite of rest's +1.25 → arms up
      pose.rUpArm.z = +1.40 * lift;
      pose.lUpArm.x = -0.10 * lift;
      pose.rUpArm.x = -0.10 * lift;
      pose.spineX = -0.10 * lift; // arch back
    }

    if (act.name === "dance") {
      // Bouncy hip sway + arm bob to a 2 Hz beat.
      const beat = aLocal * 2 * Math.PI * 1.4;
      pose.hipsZ = Math.sin(beat) * 0.18;
      pose.hipsY = Math.sin(beat) * 0.10;
      pose.spineZ = -Math.sin(beat) * 0.05;
      const armBob = Math.sin(beat);
      pose.lUpArm.z = -0.55 - armBob * 0.20;
      pose.rUpArm.z = +0.55 + armBob * 0.20;
      pose.lUpArm.x = -0.20 + armBob * 0.10;
      pose.rUpArm.x = -0.20 - armBob * 0.10;
      pose.lLoArm.x = -0.45;
      pose.rLoArm.x = -0.45;
      // Light up-down bob with the beat.
      if (g) g.position.y = 0.04 * Math.max(0, Math.sin(beat));
    }

    if (act.name === "peek") {
      const lean = Math.sin(THREE.MathUtils.clamp(aPhase, 0, 1) * Math.PI);
      pose.spineZ = lean * 0.18;
      pose.hipsZ = lean * 0.10;
    }

    if (act.name === "look_around") {
      // Big slow head turn left → right → center.
      pose.head.override = true;
      pose.head.y = Math.sin(aPhase * Math.PI * 2) * 0.55;
      pose.head.x = Math.sin(aPhase * Math.PI * 2) * 0.05;
    }

    if (act.name === "nod") {
      // Three quick yes-nods.
      pose.head.override = true;
      pose.head.x = Math.sin(aLocal * 9) * 0.25 * Math.sin(aPhase * Math.PI);
    }

    if (act.name === "cheer") {
      // Both arms up + small jumps.
      const lift = Math.sin(THREE.MathUtils.clamp(aPhase, 0, 1) * Math.PI);
      pose.lUpArm.z = -1.55 * lift;
      pose.rUpArm.z = +1.55 * lift;
      pose.lUpArm.x = -0.15 * lift;
      pose.rUpArm.x = -0.15 * lift;
      const beat = aLocal * 2 * Math.PI * 1.8;
      if (g) g.position.y = Math.max(0, Math.sin(beat)) * 0.05 * lift;
      pose.head.override = true;
      pose.head.x = -0.10 * lift; // look up at hands
    }

    if (act.name === "tap_foot") {
      // Stand on left, tap right foot to a beat.
      const beat = aLocal * 2 * Math.PI * 2.2;
      pose.rUpLeg.x = Math.max(0, Math.sin(beat)) * 0.35;
      pose.rLoLeg.x = -Math.max(0, Math.sin(beat)) * 0.6;
      pose.hipsZ = -0.05; // weight on left leg
      pose.head.override = true;
      pose.head.y = Math.sin(beat) * 0.06;
    }

    if (act.name === "bow") {
      // Forward bend + arm sweep.
      const bend = Math.sin(THREE.MathUtils.clamp(aPhase, 0, 1) * Math.PI);
      pose.spineX = -0.55 * bend;
      pose.lUpArm.z = -0.30 * bend;
      pose.rUpArm.z = +0.30 * bend;
      pose.head.override = true;
      pose.head.x = 0.20 * bend; // chin down
    }

    if (act.name === "arms_crossed") {
      // Arms folded across chest.
      const k = Math.min(1, aLocal / 0.5);
      pose.lUpArm.z = -0.55 * k;
      pose.rUpArm.z = +0.55 * k;
      pose.lUpArm.x = -0.10 * k;
      pose.rUpArm.x = -0.10 * k;
      pose.lLoArm.x = -1.55 * k;
      pose.rLoArm.x = -1.55 * k;
      pose.lLoArm.z = +0.30 * k;
      pose.rLoArm.z = -0.30 * k;
      pose.head.override = true;
      pose.head.z = Math.sin(aLocal * 0.8) * 0.05; // sassy tilt
    }

    if (act.name === "ponder") {
      // Hand to chin, head tilted, slight sway.
      const k = Math.min(1, aLocal / 0.6);
      pose.rUpArm.z = +0.55 * k;
      pose.rUpArm.x = -0.30 * k;
      pose.rLoArm.x = -1.85 * k;
      pose.rLoArm.z = -0.20 * k;
      pose.head.override = true;
      pose.head.x = -0.05;
      pose.head.z = -0.18;
      pose.head.y = Math.sin(aLocal * 0.8) * 0.06;
    }

    if (act.name === "sit_on_window") {
      // She is floating onto the window edge and sitting down!
      // To simulate sitting on the OS window: bend knees 90 deg, lift upper legs 90 deg.
      // And place her arms resting on her lap or dangling.
      const k = Math.min(1, aLocal / 0.8);
      
      // Sit down (hips drop down locally so feet don't clip as much)
      if (g) g.position.y = -0.35 * k;

      pose.lUpLeg.x = -1.5 * k;  // lift thigh up (sitting forward)
      pose.rUpLeg.x = -1.5 * k;
      pose.lLoLeg.x = 1.5 * k;   // bend knee down 90 deg
      pose.rLoLeg.x = 1.5 * k;
      
      // Arms resting on lap
      pose.lUpArm.z = -0.5 * k;
      pose.rUpArm.z = 0.5 * k;
      pose.lUpArm.x = -0.2 * k;
      pose.rUpArm.x = -0.2 * k;
      pose.lLoArm.x = -1.0 * k;
      pose.rLoArm.x = -1.0 * k;

      // Little dangling leg kicks while sitting
      const swing = Math.sin(aLocal * 1.5) * 0.15;
      pose.lLoLeg.x += swing;
      pose.rLoLeg.x -= swing;
    }

    if (act.name === "peek_from_screen_edge") {
      // She hides just off screen, then leans her spine and head in to peek!
      const distToLeft = PetMovement.currentX - PetMovement.minX;
      const isLeft = distToLeft < (PetMovement.maxX - PetMovement.currentX);
      const leanDir = isLeft ? -1 : 1; // Lean right if on left edge, left if on right edge
      
      // Wait 1.5 seconds to hide, then slowly peek out for 2 seconds, then retreat
      if (aLocal > 1.5 && aLocal < 4.0) {
        const peekAmount = Math.sin((Math.min(1, (aLocal - 1.5) / 1.0)) * Math.PI / 2); // ease in
        pose.spineZ = leanDir * 0.45 * peekAmount; // heavy lean
        pose.hipsZ = leanDir * 0.2 * peekAmount;
        
        // Hands gripping the "invisible wall"
        pose.lUpArm.z = -0.5 * peekAmount;
        pose.lUpArm.x = -0.5 * peekAmount;
        pose.rUpArm.z = 0.5 * peekAmount;
        pose.rUpArm.x = -0.5 * peekAmount;
        
        // Look towards center
        pose.head.override = true;
        pose.head.y = -leanDir * 0.3 * peekAmount;
        pose.head.z = -leanDir * 0.2 * peekAmount;
      }
    }

    if (act.name === "jump") {
      // Procedural jump physics! Anticipation (crouch) -> Spring -> Hangtime -> Land
      if (aLocal < 0.3) {
        // Crouch
        const crouch = Math.sin((aLocal / 0.3) * Math.PI / 2);
        if (g) g.position.y = -0.2 * crouch;
        pose.lLoLeg.x = 0.8 * crouch;
        pose.rLoLeg.x = 0.8 * crouch;
        pose.lUpLeg.x = -0.8 * crouch;
        pose.rUpLeg.x = -0.8 * crouch;
        pose.spineX = -0.3 * crouch; // Lean forward
        // Arms back
        pose.lUpArm.x = 0.4 * crouch;
        pose.rUpArm.x = 0.4 * crouch;
      } else if (aLocal < 1.0) {
        // Jump!
        const jumpTime = (aLocal - 0.3) / 0.7; // 0..1
        const height = Math.sin(jumpTime * Math.PI); // Parabola
        if (g) g.position.y = height * 0.6; // Jump height
        
        // Legs extend, toes point
        pose.lLoLeg.x = -0.2 * height;
        pose.rLoLeg.x = -0.2 * height;
        
        // Arms fly up!
        pose.lUpArm.z = -2.0 * height;
        pose.rUpArm.z = 2.0 * height;
        pose.lUpArm.x = -0.5 * height;
        pose.rUpArm.x = -0.5 * height;
      } else {
        // Recovery (soft landing bend)
        const land = Math.sin(((aLocal - 1.0) / 0.5) * Math.PI); // 0..1..0
        if (g) g.position.y = -0.1 * land;
        pose.lLoLeg.x = 0.4 * land;
        pose.rLoLeg.x = 0.4 * land;
      }
    }

    // ── Apply Animation Blending ──
    // Smoothly interpolate the currentPose towards the target pose to prevent snapping.
    const dampRate = Math.min(1, delta * 8.0);
    const dampObj = (curr: any, targ: any) => {
      for (const k in targ) {
        if (k === 'override' || k === 'forceFaceCamera') continue;
        if (typeof targ[k] === 'number') curr[k] += (targ[k] - curr[k]) * dampRate;
        else if (typeof targ[k] === 'object') dampObj(curr[k], targ[k]);
      }
    };
    dampObj(currentPose, pose);

    // Smooth gait energy ramp.
    const w = wander.current;
    const targetWalk = currentPose.walkPower;
    w.walkAmount += (targetWalk - w.walkAmount) * Math.min(1, delta * 4);
    const walkPower = w.walkAmount;
    w.walkPhase += delta * 2 * Math.PI * 1.6 * Math.max(0.3, walkPower);

    // Facing — walk turns toward direction of travel; everything else faces camera.
    if (pose.forceFaceCamera) w.targetFacing = Math.PI;
    w.facing += (w.targetFacing - w.facing) * Math.min(1, delta * 4);
    if (g) g.rotation.y = w.facing + currentPose.facingOffset;

    // Walking bob (only during walk; dance handles its own bob).
    if (g && act.name === "walk") {
      g.position.y = Math.abs(Math.sin(w.walkPhase)) * 0.025 * walkPower;
    } else if (g && act.name !== "dance" && act.name !== "sit_on_window" && act.name !== "jump" && act.name !== "peek_from_screen_edge") {
      g.position.y += (0 - g.position.y) * dampRate; // smooth return to floor
    }

    // ── Leg gait (only meaningful when walking) ──
    const phase = w.walkPhase;
    const legSwing = 0.55 * walkPower;
    const kneeBend = 1.05 * walkPower;
    const restKnee = 0.05;

    const lUpLeg = get(VRMHumanBoneName.LeftUpperLeg);
    const rUpLeg = get(VRMHumanBoneName.RightUpperLeg);
    const lLoLeg = get(VRMHumanBoneName.LeftLowerLeg);
    const rLoLeg = get(VRMHumanBoneName.RightLowerLeg);
    const lFoot  = get(VRMHumanBoneName.LeftFoot);
    const rFoot  = get(VRMHumanBoneName.RightFoot);

    if (lUpLeg) lUpLeg.rotation.set(
       Math.sin(phase) * legSwing + currentPose.lUpLeg.x,
       currentPose.lUpLeg.y,
       currentPose.lUpLeg.z,
    );
    if (rUpLeg) rUpLeg.rotation.set(
      -Math.sin(phase) * legSwing + currentPose.rUpLeg.x,
       currentPose.rUpLeg.y,
       currentPose.rUpLeg.z,
    );
    if (lLoLeg) lLoLeg.rotation.x = -(Math.max(0,  Math.cos(phase)) * kneeBend + restKnee) + currentPose.lLoLeg.x;
    if (rLoLeg) rLoLeg.rotation.x = -(Math.max(0, -Math.cos(phase)) * kneeBend + restKnee) + currentPose.rLoLeg.x;
    if (lFoot)  lFoot.rotation.x  =  Math.cos(phase) * 0.25 * walkPower;
    if (rFoot)  rFoot.rotation.x  = -Math.cos(phase) * 0.25 * walkPower;

    // Hip sway — gait + activity-supplied offset.
    const hips = get(VRMHumanBoneName.Hips);
    if (hips) {
      hips.rotation.z = Math.sin(phase) * 0.06 * walkPower + currentPose.hipsZ;
      hips.rotation.y = Math.sin(phase) * 0.04 * walkPower + currentPose.hipsY;
    }
    if (spine) spine.rotation.z = currentPose.spineZ;
    if (chest) chest.rotation.x += currentPose.spineX;

    // ── Arms — gait swing (during walk) + activity pose offset ──
    const lUpArm = get(VRMHumanBoneName.LeftUpperArm);
    const rUpArm = get(VRMHumanBoneName.RightUpperArm);
    const lLoArm = get(VRMHumanBoneName.LeftLowerArm);
    const rLoArm = get(VRMHumanBoneName.RightLowerArm);
    const lShoulder = get(VRMHumanBoneName.LeftShoulder);
    const rShoulder = get(VRMHumanBoneName.RightShoulder);

    const lUpRest = restRot.current.leftUpperArm  ?? REST_POSE.leftUpperArm;
    const rUpRest = restRot.current.rightUpperArm ?? REST_POSE.rightUpperArm;
    const lLoRest = restRot.current.leftLowerArm  ?? REST_POSE.leftLowerArm;
    const rLoRest = restRot.current.rightLowerArm ?? REST_POSE.rightLowerArm;
    const lShRest = restRot.current.leftShoulder  ?? REST_POSE.leftShoulder;
    const rShRest = restRot.current.rightShoulder ?? REST_POSE.rightShoulder;

    const armSwing = 0.45 * walkPower;
    if (lShoulder) lShoulder.rotation.set(
      lShRest.x + currentPose.lShoulder.x,
      lShRest.y + currentPose.lShoulder.y,
      lShRest.z + breath * 0.4 + currentPose.lShoulder.z,
    );
    if (rShoulder) rShoulder.rotation.set(
      rShRest.x + currentPose.rShoulder.x,
      rShRest.y + currentPose.rShoulder.y,
      rShRest.z - breath * 0.4 + currentPose.rShoulder.z,
    );

    if (lUpArm) lUpArm.rotation.set(
      lUpRest.x + (-Math.sin(phase) * armSwing) + currentPose.lUpArm.x,
      lUpRest.y + currentPose.lUpArm.y,
      lUpRest.z + currentPose.lUpArm.z,
    );
    if (rUpArm) rUpArm.rotation.set(
      rUpRest.x + ( Math.sin(phase) * armSwing) + currentPose.rUpArm.x,
      rUpRest.y + currentPose.rUpArm.y,
      rUpRest.z + currentPose.rUpArm.z,
    );
    if (lLoArm) lLoArm.rotation.set(
      lLoRest.x + Math.max(0,  Math.sin(phase)) * 0.35 * walkPower + currentPose.lLoArm.x,
      lLoRest.y + currentPose.lLoArm.y,
      lLoRest.z + currentPose.lLoArm.z,
    );
    if (rLoArm) rLoArm.rotation.set(
      rLoRest.x + Math.max(0, -Math.sin(phase)) * 0.35 * walkPower + currentPose.rLoArm.x,
      rLoRest.y + currentPose.rLoArm.y,
      rLoRest.z + currentPose.rLoArm.z,
    );

    // ── Reaction pulse: forward lean + brief surprise on new utterance ──
    const reactAge = t - reaction.current.t0;
    const reactPulse = reactAge > 0 && reactAge < 0.8
      ? Math.sin((reactAge / 0.8) * Math.PI)
      : 0;
    if (reaction.current.kind === "surprise") {
      setExpr(vrm, E.SURP, 0.5 * reactPulse);
    }

    // ── Emotion expressions (driven by sentiment when talking; idle = soft smile) ──
    let happy = 0, sad = 0, angry = 0, surp = sentiment.surp * 0.3;
    if (cur === "talking") {
      happy = Math.max(0.18, sentiment.happy);
      sad   = sentiment.sad;
      angry = sentiment.angry;
      surp  = Math.max(surp, sentiment.surp);
    } else if (cur === "thinking") {
      sad = Math.max(0.25, sentiment.sad * 0.5);
    } else {
      happy = 0.18 + sentiment.happy * 0.5;
      sad   = sentiment.sad * 0.4;
    }
    setExpr(vrm, E.HAPPY, happy);
    setExpr(vrm, E.SAD,   sad);
    setExpr(vrm, E.ANGRY, angry);
    setExpr(vrm, E.SURP,  Math.max(surp, reaction.current.kind === "surprise" ? 0.5 * reactPulse : 0));

    // ── Lip sync (Real-Time Audio Waveform) ──
    // The Python FormantAnalyzer scans the raw PCM bytes of the TTS audio
    // currently playing through your speakers, calculates the FFT bands,
    // and exposes the exact jaw/lip weights. We apply them instantly here!
    
    // We only apply mouth shapes if she is physically talking or if the
    // audio analyzer detects speech energy (aa/oh/ee).
    const vMouth = liveVisemes.current;
    if (vMouth.aa > 0 || vMouth.oh > 0 || vMouth.ee > 0 || vMouth.ou > 0 || vMouth.ih > 0) {
      setExpr(vrm, E.AA, vMouth.aa);
      setExpr(vrm, E.IH, vMouth.ih);
      setExpr(vrm, E.OU, vMouth.ou);
      setExpr(vrm, E.EE, vMouth.ee);
      setExpr(vrm, E.OH, vMouth.oh);
    } else {
      // Close mouth completely when silent
      setExpr(vrm, E.AA, 0);
      setExpr(vrm, E.IH, 0);
      setExpr(vrm, E.OU, 0);
      setExpr(vrm, E.EE, 0);
      setExpr(vrm, E.OH, 0);
    }

    // ── Head + neck behavior ──
    const head = get(VRMHumanBoneName.Head);
    const neck = get(VRMHumanBoneName.Neck);
    const mx = mouseRef.current.x;
    const my = mouseRef.current.y;

    // Advanced Spine IK: The body naturally leans/twists toward the cursor
    if (!pose.head.override && act.name !== "sit_on_window" && act.name !== "jump" && act.name !== "peek_from_screen_edge") {
      if (spine) {
        spine.rotation.x += my * 0.08;
        spine.rotation.y = -mx * 0.15;
      }
      if (chest) {
        chest.rotation.x += my * 0.08;
        chest.rotation.y = -mx * 0.15;
      }
    }

    if (pose.head.override) {
      if (head) {
        head.rotation.x = currentPose.head.x;
        head.rotation.y = currentPose.head.y;
        head.rotation.z = currentPose.head.z;
      }
      if (neck) neck.rotation.y = currentPose.head.y * 0.4;
    } else if (cur === "talking") {
      const baseY = Math.sin(t * 1.4) * 0.10;
      const baseX = Math.sin(t * 3.2) * 0.05;
      const tilt = sentiment.curious ? -0.18 : 0;
      const lean = sentiment.surp > 0 ? -0.10 : 0;
      if (head) {
        head.rotation.x = baseX + lean - reactPulse * 0.08;
        head.rotation.y = baseY + mx * 0.15;
        head.rotation.z = tilt;
      }
      if (neck) neck.rotation.y = baseY * 0.5;
    } else if (cur === "thinking") {
      if (head) {
        head.rotation.x = -0.05;
        head.rotation.y = Math.sin(t * 0.5) * 0.05 - 0.10;
        head.rotation.z = -0.18;
      }
    } else {
      if (head) {
        head.rotation.x = THREE.MathUtils.clamp(my * 0.20, -0.25, 0.25)
          + Math.sin(t * 1.1) * 0.03;
        head.rotation.y = THREE.MathUtils.clamp(mx * 0.35, -0.5, 0.5)
          + Math.sin(t * 0.8) * 0.04;
        head.rotation.z = 0;
      }
      if (neck) neck.rotation.y = mx * 0.10;
    }

    // ── Eye gaze (Advanced IK + Saccades) ──
    if (vrm.lookAt) {
      const s = saccade.current;
      
      // Update saccade target (Micro eye-darts) every 100-400ms
      if (t > s.nextUpdate) {
        const jitterX = (Math.random() - 0.5) * 0.15;
        const jitterY = (Math.random() - 0.5) * 0.15;
        s.target.set(mx * 0.8 + jitterX, 1.4 + my * 0.5 + jitterY, 1.5);
        s.nextUpdate = t + 0.1 + Math.random() * 0.3; // Next dart in 100-400ms
      }
      
      // Very fast lerp to the saccade target to simulate eye snapping
      s.current.lerp(s.target, Math.min(1, delta * 25.0));

      vrm.lookAt.target = vrm.lookAt.target ?? new THREE.Object3D();
      vrm.lookAt.target.position.copy(s.current);
    }

    vrm.update(delta);
  });

  if (!vrm) return null;

  return (
    <group ref={groupRef} scale={0.85}>
      <primitive object={vrm.scene} />
    </group>
  );
}
