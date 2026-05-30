import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useZendaya } from "../../store/zendayaStore";
// Drifting GPU points that orbit a sphere shell around the orb.
// Additive-blended, cheap, contributes "alive" continuous motion.
export default function Particles({ count = 600, radius = 3.5 }) {
    const pointsRef = useRef(null);
    const { positions, speeds } = useMemo(() => {
        const positions = new Float32Array(count * 3);
        const speeds = new Float32Array(count);
        for (let i = 0; i < count; i++) {
            // Random point on a sphere shell.
            const u = Math.random();
            const v = Math.random();
            const theta = 2 * Math.PI * u;
            const phi = Math.acos(2 * v - 1);
            const r = radius * (0.6 + Math.random() * 0.6);
            positions[i * 3 + 0] = r * Math.sin(phi) * Math.cos(theta);
            positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
            positions[i * 3 + 2] = r * Math.cos(phi);
            speeds[i] = 0.05 + Math.random() * 0.25;
        }
        return { positions, speeds };
    }, [count, radius]);
    const material = useMemo(() => new THREE.PointsMaterial({
        color: "#9bdcff",
        size: 0.03,
        transparent: true,
        opacity: 0.7,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
    }), []);
    const smoothed = useRef({
        speedMult: 1.0,
        radiusMult: 1.0,
    });
    useFrame((_, dt) => {
        const pts = pointsRef.current;
        if (!pts)
            return;
        // Read global AI state for particle behavior
        const zState = useZendaya.getState();
        const aiState = zState.ai;
        const sceneState = zState.scene;
        let targetSpeed = 1.0;
        let targetRadius = 1.0;
        if (sceneState === "map" || zState.docked) {
            targetSpeed = 1.2;
            targetRadius = 1.5; // Outward expansion during spatial transitions
        }
        else if (aiState === "aware") {
            targetSpeed = 1.5;
            targetRadius = 0.8; // Tighten focus
        }
        else if (aiState === "listening") {
            targetSpeed = 2.0;
            targetRadius = 0.9;
        }
        else if (aiState === "thinking") {
            targetSpeed = 4.0; // Accelerate processing
            targetRadius = 1.1;
        }
        else if (aiState === "speaking") {
            targetSpeed = 2.5;
            targetRadius = 1.2; // Radiate outward
        }
        smoothed.current.speedMult += (targetSpeed - smoothed.current.speedMult) * Math.min(1, dt * 2);
        smoothed.current.radiusMult += (targetRadius - smoothed.current.radiusMult) * Math.min(1, dt * 2);
        const arr = pts.geometry.attributes.position.array;
        for (let i = 0; i < count; i++) {
            const ix = i * 3;
            // Get base position un-rotated
            const x = arr[ix];
            const y = arr[ix + 1];
            const z = arr[ix + 2];
            // Calculate current radius of particle and pull it towards the target radius multiplier
            const currentR = Math.sqrt(x * x + y * y + z * z);
            const baseR = radius * (0.6 + (i / count) * 0.6); // approximate base r
            const targetR = baseR * smoothed.current.radiusMult;
            const pull = (targetR - currentR) * 0.05;
            const newX = x + (x / currentR) * pull;
            const newY = y + (y / currentR) * pull;
            const newZ = z + (z / currentR) * pull;
            // Rotate around Y axis at per-particle speed * state multiplier
            const rotSpeed = speeds[i] * smoothed.current.speedMult;
            const c = Math.cos(rotSpeed * dt);
            const s = Math.sin(rotSpeed * dt);
            arr[ix] = newX * c - newZ * s;
            arr[ix + 2] = newX * s + newZ * c;
            // Tiny vertical bob.
            arr[ix + 1] = newY + Math.sin((performance.now() * 0.001 + i) * 0.5) * 0.0008;
        }
        pts.geometry.attributes.position.needsUpdate = true;
        pts.rotation.y += dt * 0.02 * smoothed.current.speedMult;
    });
    return (_jsxs("points", { ref: pointsRef, children: [_jsx("bufferGeometry", { children: _jsx("bufferAttribute", { attach: "attributes-position", count: count, array: positions, itemSize: 3 }) }), _jsx("primitive", { object: material, attach: "material" })] }));
}
