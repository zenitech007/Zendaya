# Scaffold notes

The `npm create tauri-app` scaffolder generates these files we keep
unchanged:

- `src-tauri/Cargo.toml` — just the default
- `src-tauri/build.rs` — default
- `src-tauri/src/main.rs` — default
- `src-tauri/src/lib.rs` — default
- `src-tauri/icons/*` — replace with Zendaya icons later (optional)
- `src-tauri/capabilities/default.json` — default

The template overrides:

- `package.json` — adds the `sync-html.js` step
- `vite.config.js` — points root at `src/`, builds to `dist/`
- `src-tauri/tauri.conf.json` — frameless window, CSP for ports 7475/8765
- `sync-html.js` — copies `backend/zendaya_ui.html` → `src/index.html`
  with a WS URL override

`src/index.html` is **generated**, not hand-written. Edit
`backend/zendaya_ui.html` (the canonical version) and rerun the dev/build
script.

## Update sync

If you change `backend/zendaya_ui.html`, just rerun:

```bash
npm run dev    # reloads
# or
npm run tauri build
```

`sync-html.js` runs first and refreshes `src/index.html` automatically.
