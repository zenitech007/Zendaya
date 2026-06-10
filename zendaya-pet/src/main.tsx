import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";

// ---------------------------------------------------------------------------
// Global error surfacing — render any boot-time failure on screen so we don't
// just see a blank window vanish.
// ---------------------------------------------------------------------------
function showBootError(label: string, err: unknown) {
  const root = document.getElementById("root");
  const stack = err instanceof Error ? (err.stack ?? err.message) : String(err);
  const html = `
    <div style="position:fixed;inset:0;padding:20px;background:#1a0606;color:#ffd6d6;
                font-family:ui-monospace,Consolas,monospace;font-size:13px;line-height:1.5;
                white-space:pre-wrap;overflow:auto;">
      <div style="font-weight:600;font-size:15px;margin-bottom:8px;">[BOOT FAIL] ${label}</div>
      ${String(stack).replace(/[<&]/g, (c) => (c === "<" ? "&lt;" : "&amp;"))}
    </div>`;
  if (root) root.innerHTML = html;
  else document.body.insertAdjacentHTML("beforeend", html);
}

window.addEventListener("error", (e) => showBootError("window.onerror", e.error ?? e.message));
window.addEventListener("unhandledrejection", (e) => {
  const msg = String(e.reason);
  // Don't take over the screen for non-fatal Tauri permission rejections —
  // log them and move on; the rest of the app is still healthy.
  if (/not allowed|Permissions associated/i.test(msg)) {
    console.warn("[unhandledrejection ignored]", msg);
    e.preventDefault();
    return;
  }
  showBootError("unhandledrejection", e.reason);
});

// ---------------------------------------------------------------------------
// Mount React. Wrap in try/catch so even a synchronous module-level error in
// App's import chain shows up on the page.
// ---------------------------------------------------------------------------
(async () => {
  try {
    const { default: App } = await import("./App");
    const rootEl = document.getElementById("root");
    if (!rootEl) {
      showBootError("mount", "no #root element in index.html");
      return;
    }
    ReactDOM.createRoot(rootEl).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    );
  } catch (err) {
    showBootError("import App", err);
  }
})();
