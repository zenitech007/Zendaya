// Spawns `tauri dev` with WEBVIEW2_BROWSER_EXECUTABLE_FOLDER pointed at the
// bundled WebView2 runtime under src-tauri/webview2-runtime. The system
// WebView2 install on this machine is broken (installer returns E_FAIL), so
// dev mode would otherwise flash a window and die. The bundled runtime is
// only auto-used by `tauri build` via fixedRuntime; dev needs this env var.

import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { existsSync } from "node:fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const runtimeDir = resolve(projectRoot, "src-tauri", "webview2-runtime");
const webviewExe = resolve(runtimeDir, "msedgewebview2.exe");

if (!existsSync(webviewExe)) {
  console.error("[dev-with-webview] missing:", webviewExe);
  console.error("Expected msedgewebview2.exe inside src-tauri/webview2-runtime/.");
  process.exit(1);
}

console.log("[dev-with-webview] using runtime:", runtimeDir);

const env = {
  ...process.env,
  WEBVIEW2_BROWSER_EXECUTABLE_FOLDER: runtimeDir,
};

const child = spawn("npx", ["tauri", "dev"], {
  cwd: projectRoot,
  env,
  stdio: "inherit",
  shell: true,
});

child.on("exit", (code, signal) => {
  if (signal) {
    console.log(`[dev-with-webview] tauri dev exited via signal ${signal}`);
    process.exit(1);
  }
  process.exit(code ?? 0);
});

const forward = (sig) => {
  if (!child.killed) child.kill(sig);
};
process.on("SIGINT", () => forward("SIGINT"));
process.on("SIGTERM", () => forward("SIGTERM"));
