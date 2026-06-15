"""
zendaya_vision.py
=================
Screen and webcam vision tools. Captures an image, sends it to Gemini 2.5 Flash
with the user's question, returns the model's text answer.
"""

import io
import time
from typing import Optional

try:
    import mss
    _MSS_READY = True
except Exception:
    _MSS_READY = False

try:
    from PIL import Image
    _PIL_READY = True
except Exception:
    _PIL_READY = False

try:
    import cv2
    _CV2_READY = True
except Exception:
    _CV2_READY = False


def _capture_screen() -> Optional[bytes]:
    if not _MSS_READY or not _PIL_READY:
        return None
    try:
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])  # all monitors stitched
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            max_w = 1600
            if img.width > max_w:
                ratio = max_w / img.width
                img = img.resize((max_w, int(img.height * ratio)))
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            return buf.getvalue()
    except Exception as e:
        print(f"(screen capture failed: {e})")
        return None


def _capture_webcam() -> Optional[bytes]:
    if not _CV2_READY or not _PIL_READY:
        return None
    cap = None
    try:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return None
        for _ in range(5):
            cap.read()
            time.sleep(0.05)
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as e:
        print(f"(webcam capture failed: {e})")
        return None
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass


def _ask_gemini_about_image(client, image_bytes: bytes, mime: str, question: str) -> str:
    from google.genai import types
    part = types.Part.from_bytes(data=image_bytes, mime_type=mime)
    prompt = (
        "You are Zendaya, a witty AI assistant. Look at this image and answer the user "
        "concisely (2-4 sentences). Be specific about what's actually visible.\n\n"
        f"User's question: {question}"
    )
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[part, prompt],
    )
    return (resp.text or "").strip() or "I couldn't read that image clearly."


def analyze_screen(client, question: str = "What's on my screen right now?") -> str:
    if not _MSS_READY:
        return "Screen capture is unavailable — install with: pip install mss pillow"
    img_bytes = _capture_screen()
    if img_bytes is None:
        return "I couldn't grab a screenshot."
    try:
        return _ask_gemini_about_image(client, img_bytes, "image/png", question)
    except Exception as e:
        return f"I captured your screen but couldn't analyze it: {e}"


def analyze_webcam(client, question: str = "What do you see?") -> str:
    if not _CV2_READY:
        return "Webcam access is unavailable — install with: pip install opencv-python"
    img_bytes = _capture_webcam()
    if img_bytes is None:
        return "I couldn't get a frame from the webcam — it may be in use or disabled."
    try:
        return _ask_gemini_about_image(client, img_bytes, "image/jpeg", question)
    except Exception as e:
        return f"I captured a webcam frame but couldn't analyze it: {e}"


def parse_vision_request(user_text: str):
    """
    Returns ('screen' | 'webcam', question) if this looks like a vision request,
    else None.
    """
    import re
    t = user_text.lower().strip()

    screen_patterns = [
        r"\bwhat(?:'s| is| are)\s+(?:on|happening on)\s+(?:my\s+)?screen\b",
        r"\b(?:look at|read|describe|analyze|check|see)\s+(?:my\s+)?screen\b",
        r"\bwhat\s+am\s+i\s+(?:looking\s+at|seeing)\b",
        r"\b(?:take|grab|capture)\s+(?:a\s+)?screenshot\s+(?:and|to)\s+(?:tell|describe|analyze|look|read)\b",
        r"\bwhat\s+do\s+you\s+see\s+(?:on\s+)?(?:my\s+)?(?:screen|display|monitor)\b",
        r"\bread\s+(?:what'?s|whats)\s+on\s+(?:my\s+)?screen\b",
    ]
    for p in screen_patterns:
        if re.search(p, t):
            return ("screen", user_text)

    webcam_patterns = [
        r"\bwhat\s+do\s+you\s+see\b(?!\s+on\s+(?:my\s+)?screen)",
        r"\b(?:look at|use|check|open)\s+(?:the\s+)?(?:webcam|camera)\b",
        r"\bwho\s+(?:am\s+i|is\s+(?:in\s+front\s+of|with))\b",
        r"\bwhat\s+(?:am\s+i\s+wearing|do\s+i\s+look\s+like)\b",
        r"\b(?:through|using)\s+(?:the\s+)?camera\b",
    ]
    for p in webcam_patterns:
        if re.search(p, t):
            return ("webcam", user_text)

    return None


def diagnostics() -> str:
    lines = ["Vision diagnostics:"]
    lines.append(f"  mss (screen):     {'OK' if _MSS_READY else 'MISSING (pip install mss)'}")
    lines.append(f"  Pillow:           {'OK' if _PIL_READY else 'MISSING (pip install pillow)'}")
    lines.append(f"  opencv (webcam):  {'OK' if _CV2_READY else 'MISSING (pip install opencv-python)'}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(diagnostics())
