// Sync the canonical HUD HTML from the Python backend into src/index.html
// so the browser-served version (http://127.0.0.1:7475/ui) and the bundled
// Tauri version stay identical.
//
// The HUD's WS URL is overridden to ws://127.0.0.1:7475/ws (the brain's WS),
// using the existing ?ws= query param via a small <script> inject.
import { copyFileSync, readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(__dirname, '../backend/zendaya_ui.html');
const DEST_DIR = resolve(__dirname, 'src');
const DEST = join(DEST_DIR, 'index.html');

if (!existsSync(SRC)) {
  console.error(`[sync-html] source not found: ${SRC}`);
  process.exit(1);
}
if (!existsSync(DEST_DIR)) mkdirSync(DEST_DIR, { recursive: true });

let html = readFileSync(SRC, 'utf8');

// Force the WS URL to the brain's port (7475/ws) when running inside Tauri.
// We don't edit the source HTML — we patch a tiny inline override before </body>.
const overrideTag = `\n<script>
// Tauri override: point at the Python brain's WS bridge.
(() => {
  if (window.location.search.includes('ws=')) return;
  const u = new URL(window.location.href);
  u.searchParams.set('ws', 'ws://127.0.0.1:7475/ws');
  window.history.replaceState(null, '', u.toString());
})();
</script>\n`;

html = html.replace('</body>', overrideTag + '</body>');

writeFileSync(DEST, html, 'utf8');
console.log(`[sync-html] wrote ${DEST} (${html.length} bytes)`);
