import { useEffect, useRef } from "react";

import { invoke } from "@tauri-apps/api/core";

// Global bridge between Avatar.tsx (3D) and useWindowRoam (Tauri Window)
export const PetMovement = {
  active: false,
  targetX: 0,
  targetY: 0,
  currentX: 0,
  currentY: 0,
  minX: 0,
  maxX: 1920,
  minY: 0,
  maxY: 1080,
  setTarget(x: number, y: number) {
    this.targetX = x;
    // We ignore targetY now unless it's a forced teleport, because gravity handles Y!
    // But we still store it in case she needs to float up to a window edge to sit.
    this.targetY = y;
    this.active = true;
  }
};

interface WindowInfo {
  title: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

const EDGE_INSET = 16;       
const TASKBAR_INSET = 80;    
const STEP_PX_PER_S = 180;   // Walking speed
const GRAVITY_PX_PER_S = 1500; // Gravity acceleration
const TERMINAL_VELOCITY = 1000;
const FOOT_OFFSET_Y = 780; // Distance from top of 420x820 window to her feet

export function useWindowRoam(enabled: boolean = true) {
  const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
  const cancelRef = useRef(false);

  useEffect(() => {
    if (!enabled || !isTauri) return;
    cancelRef.current = false;

    let raf = 0;
    let cancelled = false;

    (async () => {
      try {
        const { getCurrentWindow, currentMonitor } = await import("@tauri-apps/api/window");
        const { PhysicalPosition } = await import("@tauri-apps/api/dpi");
        const win = getCurrentWindow();
        
        // Initialize current position & monitor bounds
        const mon = await currentMonitor();
        const size = await win.outerSize();
        if (mon) {
          PetMovement.minX = mon.position.x + EDGE_INSET;
          PetMovement.maxX = mon.position.x + mon.size.width - size.width - EDGE_INSET;
          PetMovement.minY = mon.position.y + EDGE_INSET;
          PetMovement.maxY = mon.position.y + mon.size.height - size.height - TASKBAR_INSET;
          
          // "Walk in" instead of just appearing!
          // Start the OS window physically off-screen to the right
          PetMovement.currentX = mon.position.x + mon.size.width + size.width;
          PetMovement.currentY = PetMovement.maxY; // Walk along the bottom
          
          // Command her to walk to the center of the screen
          PetMovement.targetX = mon.position.x + (mon.size.width / 2) - (size.width / 2);
          PetMovement.targetY = PetMovement.maxY;
          PetMovement.active = true;
          
          // Immediately teleport the window off-screen so she can walk in
          await win.setPosition(new PhysicalPosition(
            Math.round(PetMovement.currentX), 
            Math.round(PetMovement.currentY)
          ));
        } else {
          const initialPos = await win.outerPosition();
          PetMovement.currentX = initialPos.x;
          PetMovement.currentY = initialPos.y;
          PetMovement.targetX = initialPos.x;
          PetMovement.targetY = initialPos.y;
        }

        let lastTick = performance.now();
        let velocityY = 0;
        let platforms: WindowInfo[] = [];

        // Poll for active windows to build the physics NavMesh
        const pollNavMesh = async () => {
          if (cancelled) return;
          try {
            const wins = await invoke<WindowInfo[]>("get_active_windows");
            if (wins) platforms = wins;
          } catch {}
          setTimeout(pollNavMesh, 1000); // Rebuild NavMesh every 1 second
        };
        pollNavMesh();

        const tick = async () => {
          if (cancelled) return;
          const now = performance.now();
          const dtS = Math.min(0.1, (now - lastTick) / 1000);
          lastTick = now;

          let newX = PetMovement.currentX;
          let newY = PetMovement.currentY;

          // Horizontal movement (AI controlled)
          if (PetMovement.active) {
            const dx = PetMovement.targetX - PetMovement.currentX;
            if (Math.abs(dx) > 1) {
              const dir = Math.sign(dx);
              newX += dir * Math.min(Math.abs(dx), STEP_PX_PER_S * dtS);
            }
          }

          // Vertical physics (Gravity & Collisions)
          // Exception: If she is specifically targeting a sit, we let her float there.
          const isSitting = PetMovement.active && PetMovement.targetY < PetMovement.maxY - 100;
          
          if (isSitting) {
            const dy = PetMovement.targetY - PetMovement.currentY;
            if (Math.abs(dy) > 1) {
               newY += Math.sign(dy) * Math.min(Math.abs(dy), STEP_PX_PER_S * 2 * dtS);
            }
          } else {
            // Apply gravity
            velocityY += GRAVITY_PX_PER_S * dtS;
            velocityY = Math.min(velocityY, TERMINAL_VELOCITY);
            newY += velocityY * dtS;

            // Check floor collision
            if (newY >= PetMovement.maxY) {
              newY = PetMovement.maxY;
              velocityY = 0;
            }

            // Check platform (window) collisions
            // Her foot X is roughly the center of her window
            const footX = newX + (size.width / 2);
            const prevFootY = PetMovement.currentY + FOOT_OFFSET_Y;
            const nextFootY = newY + FOOT_OFFSET_Y;

            for (const plat of platforms) {
              // Is she horizontally above the window?
              if (footX >= plat.x && footX <= plat.x + plat.width) {
                // Did her feet pass through the top edge of the window in this frame?
                if (prevFootY <= plat.y && nextFootY >= plat.y) {
                  // Hit the platform! Snap to the top edge.
                  newY = plat.y - FOOT_OFFSET_Y;
                  velocityY = 0;
                  break; // Stop falling
                }
              }
            }
          }

          // Only move OS window if position actually changed
          if (Math.abs(newX - PetMovement.currentX) > 0.1 || Math.abs(newY - PetMovement.currentY) > 0.1) {
            PetMovement.currentX = newX;
            PetMovement.currentY = newY;
            await win.setPosition(new PhysicalPosition(
              Math.round(PetMovement.currentX), 
              Math.round(PetMovement.currentY)
            ));
          } else if (PetMovement.active && Math.abs(PetMovement.targetX - PetMovement.currentX) <= 1) {
            // Reached destination
            PetMovement.active = false;
          }

          raf = requestAnimationFrame(() => tick());
        };

        raf = requestAnimationFrame(() => tick());
      } catch (err) {
        console.warn("[useWindowRoam] disabled:", err);
      }
    })();

    return () => {
      cancelled = true;
      cancelRef.current = true;
      if (raf) cancelAnimationFrame(raf);
    };
  }, [enabled, isTauri]);
}
