import { useZendaya, type ModuleId } from "../store/zendayaStore";

const MODULES: ModuleId[] = ["map", "calculator", "clock", "notes", "weather"];

/** Open the world-map scene. */
export function openMap() {
  const z = useZendaya.getState();
  z.setScene("map");
  z.setActiveModule("map");
  z.setPanel("globe");
}

/** Reset to the idle hologram (closes any map/module/panel). */
export function goHome() {
  const z = useZendaya.getState();
  z.setScene("main");
  z.setActiveModule("none");
  z.setPanel("none");
}

/** Activate a module by id; ignores unknown ids. `corner` (bl/br) is optional. */
export function openModule(name: string, corner?: string) {
  const z = useZendaya.getState();
  if (!MODULES.includes(name as ModuleId)) return;
  if (corner === "bl" || corner === "br") z.setDockCorner(corner);
  z.setActiveModule(name as ModuleId);
  if (name === "map") {
    z.setScene("map");
    z.setPanel("globe");
  }
}

/** Switch theme by id. setTheme silently ignores unknown ids. */
export function setThemeById(id: string) {
  useZendaya.getState().setTheme(id);
}

export function dock() { useZendaya.getState().setDocked(true); }
export function undock() { useZendaya.getState().setDocked(false); }
export function minimize() { useZendaya.getState().setMinimized(true); }
export function restore() { useZendaya.getState().setMinimized(false); }
export function activateVoice() { useZendaya.getState().setVoiceActive(true); }
export function deactivateVoice() { useZendaya.getState().setVoiceActive(false); }
export function showTerminal() { useZendaya.getState().setTerminalOpen(true); }
export function hideTerminal() { useZendaya.getState().setTerminalOpen(false); }
export function showNotification(text: string) {
  if (text) useZendaya.getState().pushNotification(text);
}
