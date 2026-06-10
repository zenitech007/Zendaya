"""
zendaya_perception — webcam-driven face presence/gaze + hand gesture input.

Single shared OpenCV capture, MediaPipe Tasks for face detection and
gesture recognition. Designed to be a soft dependency: if cv2 / mediapipe
are missing or the webcam can't be opened, the module logs a single
warning and stays quiet — Zendaya keeps running.

Public API:
    start(on_gesture=None)   # spawn the daemon thread
    stop()
    get_face() -> dict       # {"present": bool, "x": float, "y": float, "ts": float}
    pop_gestures() -> list   # drain queued gesture events
    get_last_gesture() -> dict
    set_enabled(face=None, gestures=None)
    is_active() -> dict      # for HUD
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Optional

# --- Soft deps ---------------------------------------------------------
try:
    import cv2
    _CV2_READY = True
except Exception:
    _CV2_READY = False

try:
    import mediapipe as mp  # type: ignore
    _MP_READY = True
except Exception:
    _MP_READY = False


# --- State -------------------------------------------------------------
_LOCK = threading.Lock()
_FACE = {"present": False, "x": 0.0, "y": 0.0, "ts": 0.0}
_LAST_GESTURE = {"name": "none", "ts": 0.0}
_GESTURE_Q: "queue.Queue[dict]" = queue.Queue(maxsize=16)
_STOP = threading.Event()
_THREAD: Optional[threading.Thread] = None
_FACE_ENABLED = True
_GESTURES_ENABLED = True
_ACTIVE = {"face": False, "gestures": False, "started": False}

# Smoothing on face xy (0–1 lerp factor toward latest)
_SMOOTH = 0.30
# Decay face presence to absent after this many seconds without an update
_FACE_DECAY_S = 1.0
# Per-gesture debounce (don't fire same name more than once per N seconds)
_GESTURE_DEBOUNCE_S = 1.0


# --- Public getters ----------------------------------------------------
def get_face() -> dict:
    with _LOCK:
        snap = dict(_FACE)
    if (time.time() - snap["ts"]) > _FACE_DECAY_S:
        snap["present"] = False
        snap["x"] = 0.0
        snap["y"] = 0.0
    return snap


def pop_gestures() -> list:
    out = []
    while True:
        try:
            out.append(_GESTURE_Q.get_nowait())
        except queue.Empty:
            break
    return out


def get_last_gesture() -> dict:
    with _LOCK:
        return dict(_LAST_GESTURE)


def is_active() -> dict:
    with _LOCK:
        return dict(_ACTIVE)


def set_enabled(face: Optional[bool] = None, gestures: Optional[bool] = None) -> None:
    global _FACE_ENABLED, _GESTURES_ENABLED
    if face is not None:
        _FACE_ENABLED = bool(face)
    if gestures is not None:
        _GESTURES_ENABLED = bool(gestures)


# --- Loop --------------------------------------------------------------
def _loop(on_gesture: Optional[Callable[[str], None]]) -> None:
    if not _CV2_READY:
        print("(perception: opencv-python missing — vision disabled. pip install opencv-python)")
        return
    if not _MP_READY:
        print("(perception: mediapipe missing — vision disabled. pip install mediapipe)")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("(perception: couldn't open default webcam — vision disabled)")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

    # Use the older Solutions API — wheel availability is much better than
    # the new Tasks API on Windows + Python 3.11/3.12 right now.
    face_solution = None
    gesture_solution = None
    try:
        face_solution = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
    except Exception as e:
        print(f"(perception: face detector init failed: {e})")
    try:
        # MediaPipe doesn't expose a gesture classifier in the Solutions API,
        # but Hands gives landmarks; we classify manually below.
        gesture_solution = mp.solutions.hands.Hands(
            max_num_hands=1,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.5,
        )
    except Exception as e:
        print(f"(perception: hands tracker init failed: {e})")

    with _LOCK:
        _ACTIVE["face"] = face_solution is not None
        _ACTIVE["gestures"] = gesture_solution is not None
        _ACTIVE["started"] = True

    print(
        "(perception: webcam open — "
        f"face={'on' if face_solution else 'off'}, "
        f"gestures={'on' if gesture_solution else 'off'})"
    )

    last_gesture_ts: dict[str, float] = {}
    smoothed_x = 0.0
    smoothed_y = 0.0

    try:
        while not _STOP.is_set():
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue

            # Mirror so left/right matches what the user sees
            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # ---- Face ---------------------------------------------------
            if face_solution is not None and _FACE_ENABLED:
                try:
                    res = face_solution.process(rgb)
                except Exception:
                    res = None
                if res and res.detections:
                    # Pick the largest detection by bounding box area.
                    best = max(
                        res.detections,
                        key=lambda d: (
                            d.location_data.relative_bounding_box.width
                            * d.location_data.relative_bounding_box.height
                        ),
                    )
                    box = best.location_data.relative_bounding_box
                    cx = box.xmin + box.width / 2.0       # 0..1
                    cy = box.ymin + box.height / 2.0      # 0..1
                    # Map to [-1, 1] camera coords, gentle smoothing
                    target_x = (cx - 0.5) * 2.0
                    target_y = (cy - 0.5) * 2.0
                    smoothed_x += (target_x - smoothed_x) * _SMOOTH
                    smoothed_y += (target_y - smoothed_y) * _SMOOTH
                    with _LOCK:
                        _FACE["present"] = True
                        _FACE["x"] = float(smoothed_x)
                        _FACE["y"] = float(smoothed_y)
                        _FACE["ts"] = time.time()

            # ---- Gestures ---------------------------------------------
            if gesture_solution is not None and _GESTURES_ENABLED:
                try:
                    g_res = gesture_solution.process(rgb)
                except Exception:
                    g_res = None
                if g_res and g_res.multi_hand_landmarks:
                    landmarks = g_res.multi_hand_landmarks[0].landmark
                    name = _classify_gesture(landmarks)
                    if name != "none":
                        now = time.time()
                        last_ts = last_gesture_ts.get(name, 0.0)
                        if (now - last_ts) >= _GESTURE_DEBOUNCE_S:
                            last_gesture_ts[name] = now
                            event = {"name": name, "ts": now}
                            with _LOCK:
                                _LAST_GESTURE.update(event)
                            try:
                                _GESTURE_Q.put_nowait(event)
                            except queue.Full:
                                pass
                            if on_gesture is not None:
                                # Run in a worker so a slow handler doesn't
                                # stall the perception loop.
                                threading.Thread(
                                    target=lambda: _safe_call(on_gesture, name),
                                    daemon=True,
                                ).start()

            # ~15 fps cap; webcam read already throttles us a bit.
            time.sleep(0.03)

    except Exception as e:
        print(f"(perception loop crashed: {e})")
    finally:
        try:
            cap.release()
        except Exception:
            pass
        try:
            if face_solution is not None:
                face_solution.close()
            if gesture_solution is not None:
                gesture_solution.close()
        except Exception:
            pass
        with _LOCK:
            _ACTIVE["face"] = False
            _ACTIVE["gestures"] = False
            _ACTIVE["started"] = False


def _safe_call(fn: Callable[[str], None], name: str) -> None:
    try:
        fn(name)
    except Exception as e:
        print(f"(perception on_gesture handler error: {e})")


# --- Hand-landmark gesture classifier ---------------------------------
# Landmark indices (MediaPipe Hands):
#   0 wrist
#   4 thumb tip,   3 thumb ip
#   8 index tip,   6 index pip
#  12 middle tip, 10 middle pip
#  16 ring tip,   14 ring pip
#  20 pinky tip,  18 pinky pip
def _is_extended(tip, pip) -> bool:
    """Finger is roughly extended if its tip is further from the wrist than its PIP joint."""
    return tip.y < pip.y - 0.02   # in image coords y grows downward


def _classify_gesture(lm) -> str:
    try:
        thumb_up = lm[4].y < lm[3].y - 0.04
        index_up = _is_extended(lm[8], lm[6])
        middle_up = _is_extended(lm[12], lm[10])
        ring_up = _is_extended(lm[16], lm[14])
        pinky_up = _is_extended(lm[20], lm[18])
    except Exception:
        return "none"

    fingers = [index_up, middle_up, ring_up, pinky_up]
    n_up = sum(fingers)

    # All four fingers folded + thumb up → Thumb_Up
    if thumb_up and n_up == 0:
        return "Thumb_Up"
    # All five up → Open_Palm
    if thumb_up and n_up == 4:
        return "Open_Palm"
    # All folded → Closed_Fist
    if not thumb_up and n_up == 0:
        return "Closed_Fist"
    # Index + middle up only → Victory
    if index_up and middle_up and not ring_up and not pinky_up:
        return "Victory"
    # Only index up → Pointing_Up
    if index_up and not middle_up and not ring_up and not pinky_up:
        return "Pointing_Up"
    return "none"


# --- Lifecycle --------------------------------------------------------
def start(on_gesture: Optional[Callable[[str], None]] = None) -> Optional[threading.Thread]:
    global _THREAD
    if _THREAD is not None and _THREAD.is_alive():
        return _THREAD
    _STOP.clear()
    _THREAD = threading.Thread(
        target=_loop, args=(on_gesture,), daemon=True, name="zendaya-perception"
    )
    _THREAD.start()
    return _THREAD


def stop() -> None:
    _STOP.set()


def diagnostics() -> str:
    return (
        f"opencv: {'OK' if _CV2_READY else 'MISSING'} | "
        f"mediapipe: {'OK' if _MP_READY else 'MISSING'} | "
        f"face_enabled: {_FACE_ENABLED} | gestures_enabled: {_GESTURES_ENABLED} | "
        f"active: {_ACTIVE}"
    )
