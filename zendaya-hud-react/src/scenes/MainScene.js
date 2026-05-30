import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useRef, useEffect } from "react";
import { useFrame } from "@react-three/fiber";
import Orb from "../components/Orb/Orb";
import MapModule from "../components/MapModule/MapModule";
import { useZendaya } from "../store/zendayaStore";
import { dockOrbShowMap, undockOrbHideMap } from "../animations";
export default function MainScene() {
    const orbGroup = useRef(null);
    const mapGroup = useRef(null);
    const docked = useZendaya((s) => s.docked);
    const scene = useZendaya((s) => s.scene);
    const activeModule = useZendaya((s) => s.activeModule);
    const dockCorner = useZendaya((s) => s.dockCorner);
    const showMap3D = activeModule === "map" || scene === "map";
    useEffect(() => {
        if (!orbGroup.current || !mapGroup.current)
            return;
        const targets = { orb: orbGroup.current, map: mapGroup.current };
        const tl = docked || showMap3D
            ? dockOrbShowMap(targets)
            : undockOrbHideMap(targets);
        return () => {
            tl.kill();
        };
    }, [docked, showMap3D, dockCorner]);
    useFrame(() => {
        // Orb stays still — no wobble, no rotation drift.
    });
    return (_jsxs(_Fragment, { children: [_jsx("group", { ref: orbGroup, children: _jsx(Orb, { radius: 1.0 }) }), _jsx("group", { ref: mapGroup, scale: [0.3, 0.3, 0.3], position: [0, 0, -1.5], children: _jsx(MapModule, {}) }), _jsx("ambientLight", { intensity: 0.7 })] }));
}
