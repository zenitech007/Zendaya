"""Print a pairing QR (or its JSON payload) for the Zendaya Android app.

Reads ZENDAYA_BIND_HOST + ZENDAYA_MOBILE_TOKEN from the environment/.env and
emits {"host","port","token"} as an ASCII QR if the `qrcode` package is
available, else prints the raw JSON to paste into any QR generator.
"""
from __future__ import annotations

import json
import os
import socket
import sys

try:
    from dotenv import load_dotenv  # already a backend dep
    load_dotenv()
except Exception:
    pass

HOST = os.environ.get("ZENDAYA_BIND_HOST", "127.0.0.1").strip()
PORT = int(os.environ.get("ZENDAYA_STATE_PORT", "7475"))
TOKEN = os.environ.get("ZENDAYA_MOBILE_TOKEN", "").strip()


def _tailscale_ip() -> str | None:
    """Best-effort discovery of this machine's Tailscale IP (CGNAT 100.64/10)."""
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        infos = []
    for _f, _t, _p, _c, sa in infos:
        ip = sa[0]
        # Tailscale hands out addresses in 100.64.0.0/10 (100.64.x – 100.127.x).
        if ip.startswith("100."):
            try:
                second = int(ip.split(".")[1])
            except (IndexError, ValueError):
                continue
            if 64 <= second <= 127:
                return ip
    return None


def main() -> int:
    if not TOKEN:
        print("ERROR: ZENDAYA_MOBILE_TOKEN is not set in your .env.")
        return 1

    host = HOST
    if HOST in ("127.0.0.1", "localhost"):
        print("WARNING: ZENDAYA_BIND_HOST is localhost — the phone cannot reach it.")
        print("         Set it to 0.0.0.0 (or your Tailscale IP) and restart.")
    elif HOST in ("0.0.0.0", "::"):
        # 0.0.0.0 means "bind all interfaces" — great for the server, but the
        # phone needs a concrete address. Put the Tailscale IP in the QR.
        ts = _tailscale_ip()
        if ts:
            host = ts
            print(f"Resolved Tailscale IP for the QR: {ts}")
        else:
            print("WARNING: bind host is 0.0.0.0 but no Tailscale IP (100.x) was found.")
            print("         Is Tailscale installed and connected on this PC?")
            print("         The QR below uses 0.0.0.0, which the phone CANNOT connect to.")

    payload = json.dumps({"host": host, "port": PORT, "token": TOKEN})
    print("\nPairing payload:\n  " + payload + "\n")

    try:
        import qrcode  # type: ignore
    except Exception:
        print("(`pip install qrcode[pil]` to render a scannable QR, or paste the")
        print(" payload above into any QR generator and scan it with the app.)")
        return 0

    qr = qrcode.QRCode(border=2)
    qr.add_data(payload)
    qr.make(fit=True)

    # 1) Save a PNG and open it — the most reliably scannable option on Windows.
    saved = None
    try:
        img = qr.make_image(fill_color="black", back_color="white")
        saved = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pairing_qr.png")
        img.save(saved)
        print(f"QR image saved: {saved}")
        if sys.platform.startswith("win"):
            os.startfile(saved)  # type: ignore[attr-defined]
            print("(opened it in your photo viewer - scan it from there)")
    except Exception as exc:  # pragma: no cover - image backend optional
        print(f"(could not save QR image: {exc})")

    # 2) Also try an ASCII QR in the terminal (UTF-8 permitting).
    try:
        prev = None
        if sys.platform.startswith("win"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
            except Exception:
                prev = "skip"
        if prev != "skip":
            print()
            qr.print_ascii(invert=True)
    except Exception:
        if not saved:
            print("(terminal can't render the QR here — use the payload above.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
