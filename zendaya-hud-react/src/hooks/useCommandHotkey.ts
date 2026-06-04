import { useEffect } from "react";
import { useZendaya } from "../store/zendayaStore";

/** Global keyboard control for the command terminal:
 *  Ctrl/Cmd+K toggles it; Escape closes it when open. */
export function useCommandHotkey() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        const s = useZendaya.getState();
        s.setTerminalOpen(!s.terminalOpen);
      } else if (e.key === "Escape" && useZendaya.getState().terminalOpen) {
        useZendaya.getState().setTerminalOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
