"""
zendaya_uivision — screenshot + Gemini vision + pyautogui UI control.

For apps with no CLI: take a screenshot, ask Gemini "where on this screen is
the X button?", get back pixel coordinates, and click. Every action is
confirmation-gated when it's destructive (typing or clicking).

Public API:
    capture_screen(name=None)          -> str          # PNG into ~/Zendaya/screenshots/
    describe_screen(question="...")    -> str          # Gemini answers about what's on screen
    locate_on_screen(target_desc)      -> dict | str   # {"x":..,"y":..,"label":..} or error
    click_target(target_desc)          -> str          # stages confirm; clicks after yes
    type_text(text)                    -> str          # stages confirm; types after yes
    move_mouse(x, y)                   -> str
    press_key(key)                     -> str

PyAutoGUI's failsafe (move mouse to top-left to abort) stays on. We do NOT
disable it, even though we own the input — the user must always be able to
break out by slamming the mouse into a corner.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

_SHOT_DIR = Path(os.path.expanduser("~/Zendaya/screenshots"))
_SHOT_DIR.mkdir(parents=True, exist_ok=True)


def _pyautogui():
    try:
        import pyautogui  # noqa: F401
        return pyautogui, ""
    except Exception as e:
        return None, f"pyautogui isn't installed. Run: `pip install pyautogui pillow` ({e})."


def _gemini():
    try:
        import zendaya as _z
        return getattr(_z, "_gemini_client", None), getattr(_z, "_GEMINI_READY", False)
    except Exception:
        return None, False


def _mem() -> Optional[dict]:
    try:
        import zendaya as _z
        return getattr(_z, "MEM", None)
    except Exception:
        return None


def capture_screen(name: Optional[str] = None) -> str:
    pg, err = _pyautogui()
    if err:
        return err
    safe = re.sub(r"[^A-Za-z0-9._\-]+", "_", name or f"screen-{int(time.time())}").strip("_")
    if not safe.lower().endswith(".png"):
        safe += ".png"
    out = _SHOT_DIR / safe
    try:
        img = pg.screenshot()
        img.save(str(out))
        return str(out)
    except Exception as e:
        return f"Screenshot failed: {e}"


def _ask_gemini_about_image(image_path: str, prompt: str) -> str:
    client, ready = _gemini()
    if not ready or client is None:
        return "Gemini is offline — can't analyse the screen."
    try:
        from PIL import Image
        img = Image.open(image_path)
    except Exception as e:
        return f"Couldn't open the screenshot: {e}"
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, img],
        )
        return (resp.text or "").strip()
    except Exception as e:
        return f"Gemini vision call failed: {e}"


def describe_screen(question: str = "Describe what's currently on the screen.") -> str:
    path = capture_screen()
    if not os.path.isfile(path):
        return path  # error from capture
    return _ask_gemini_about_image(path, question)


_COORD_RE = re.compile(r'"?x"?\s*[:=]\s*(-?\d+).{0,40}?"?y"?\s*[:=]\s*(-?\d+)', re.I | re.S)


def locate_on_screen(target_desc: str) -> Dict[str, Any] | str:
    """Ask Gemini for pixel coordinates of `target_desc`. Returns a dict or an error string."""
    path = capture_screen()
    if not os.path.isfile(path):
        return path
    pg, err = _pyautogui()
    if err:
        return err
    width, height = pg.size()
    prompt = (
        f"You are looking at a {width}x{height} pixel screenshot. The user wants to interact with: "
        f"«{target_desc}». Reply with ONLY a JSON object of the form "
        '{"x": <int>, "y": <int>, "label": "<short description of what you found>"} '
        "where x,y is the centre of the target in pixels. If you can't find it, "
        'reply {"x": null, "y": null, "label": "not found"}. No prose, no markdown.'
    )
    answer = _ask_gemini_about_image(path, prompt)
    try:
        data = json.loads(answer.strip().strip("`"))
    except Exception:
        m = _COORD_RE.search(answer)
        if not m:
            return f"Couldn't parse coordinates from Gemini: {answer[:300]}"
        data = {"x": int(m.group(1)), "y": int(m.group(2)), "label": "(parsed from text)"}
    x, y = data.get("x"), data.get("y")
    if not isinstance(x, int) or not isinstance(y, int):
        return f"Target not found on screen: {data.get('label', '?')}"
    if x < 0 or y < 0 or x > width or y > height:
        return f"Coordinates {x},{y} are outside the {width}x{height} screen."
    return {"x": x, "y": y, "label": data.get("label", target_desc)}


def click_target(target_desc: str) -> str:
    located = locate_on_screen(target_desc)
    if isinstance(located, str):
        return located
    mem = _mem()
    if mem is None:
        return "Memory isn't available — can't stage the click."
    mem["pending_confirm"] = {
        "action": "ui_click",
        "x": located["x"],
        "y": located["y"],
        "label": located["label"],
        "ts": time.time(),
    }
    return (
        f"Found '{located['label']}' at ({located['x']}, {located['y']}). "
        "Say yes to click, or no to cancel."
    )


def confirm_ui_click(pending: Dict) -> str:
    pg, err = _pyautogui()
    if err:
        return err
    x, y = pending.get("x"), pending.get("y")
    if not isinstance(x, int) or not isinstance(y, int):
        return "Lost the click coordinates."
    try:
        pg.moveTo(x, y, duration=0.25)
        pg.click()
        return f"Clicked at ({x}, {y})."
    except Exception as e:
        return f"Click failed: {e}"


def type_text(text: str) -> str:
    if not text:
        return "Nothing to type."
    mem = _mem()
    if mem is None:
        return "Memory isn't available — can't stage the typing."
    mem["pending_confirm"] = {
        "action": "ui_type",
        "text": text,
        "ts": time.time(),
    }
    preview = text if len(text) <= 60 else text[:57] + "..."
    return f"Ready to type «{preview}» into the active window. Say yes to type, no to cancel."


def confirm_ui_type(pending: Dict) -> str:
    pg, err = _pyautogui()
    if err:
        return err
    text = pending.get("text") or ""
    try:
        pg.typewrite(text, interval=0.02)
        return f"Typed {len(text)} characters."
    except Exception as e:
        return f"Typing failed: {e}"


def move_mouse(x: int, y: int) -> str:
    pg, err = _pyautogui()
    if err:
        return err
    try:
        pg.moveTo(int(x), int(y), duration=0.2)
        return f"Mouse moved to ({x}, {y})."
    except Exception as e:
        return f"Mouse move failed: {e}"


def press_key(key: str) -> str:
    pg, err = _pyautogui()
    if err:
        return err
    try:
        pg.press(key)
        return f"Pressed {key}."
    except Exception as e:
        return f"Key press failed: {e}"


# --- Autonomous Agent Entrypoints (No Confirmation) ---

def agent_click_target(target_desc: str) -> str:
    """Agentic entrypoint: Locate and immediately click a target without staging for user confirmation."""
    located = locate_on_screen(target_desc)
    if isinstance(located, str):
        return located # Error string
    pg, err = _pyautogui()
    if err:
        return err
    x, y = located["x"], located["y"]
    try:
        pg.moveTo(x, y, duration=0.25)
        pg.click()
        return f"Successfully clicked '{located['label']}' at ({x}, {y})."
    except Exception as e:
        return f"Failed to click target: {e}"


def agent_type_text(text: str) -> str:
    """Agentic entrypoint: Type text immediately without staging for user confirmation."""
    pg, err = _pyautogui()
    if err:
        return err
    if not text:
        return "Nothing to type."
    try:
        pg.typewrite(text, interval=0.02)
        return f"Successfully typed {len(text)} characters."
    except Exception as e:
        return f"Failed to type: {e}"


def agent_press_key(key: str) -> str:
    """Agentic entrypoint: Press a hotkey immediately."""
    pg, err = _pyautogui()
    if err:
        return err
    try:
        if "+" in key:
            keys = [k.strip() for k in key.split("+")]
            pg.hotkey(*keys)
        else:
            pg.press(key.strip())
        return f"Successfully pressed '{key}'."
    except Exception as e:
        return f"Failed to press key: {e}"

