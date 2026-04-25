import { useEffect } from "react";
import { useSystemStore } from "@/hooks/useSystemStore"; // Assuming this path

// Only heavy stream when UI explicitly activates
export function useSystemMonitor(uiActive = false) {
  const { initSocket, stopSocket, setUIActive } = useSystemStore();

  useEffect(() => {
    setUIActive(uiActive);    // mark UI usage
    initSocket();           // always start daemon

    return () => {
      if (uiActive) stopSocket(); // only stop if dashboard was active
    };
  }, [uiActive, initSocket, stopSocket, setUIActive]);
}

