# Zendaya — Godot 4 frontend

This is the visual face for Zendaya. The brain runs in Python
(`backend/zendaya.py`), this folder just renders the VRM avatar and
forwards chat input.

**Read [SETUP_GUIDE.md](SETUP_GUIDE.md) first** — it walks through
installing the VRM importer addon, dragging the `.vrm` into the scene,
and verifying the transparent always-on-top window.

Quick sanity check once everything is wired up:

```
# terminal 1
cd backend
python zendaya.py
# look for: 🪟 State server: http://127.0.0.1:7475

# terminal 2
curl http://127.0.0.1:7475/health
```

Then open this folder in Godot 4 and press **F5**.
