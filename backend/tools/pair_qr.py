"""Print a pairing QR (or its JSON payload) for the Zendaya Android app.

Reads ZENDAYA_BIND_HOST + ZENDAYA_MOBILE_TOKEN from the environment/.env and
emits {"host","port","token"} as an ASCII QR if the `qrcode` package is
available, else prints the raw JSON to paste into any QR generator.
"""
from __future__ import annotations

import json
import os
import sys

try:
    from dotenv import load_dotenv  # already a backend dep
    load_dotenv()
except Exception:
    pass

HOST = os.environ.get("ZENDAYA_BIND_HOST", "127.0.0.1").strip()
PORT = int(os.environ.get("ZENDAYA_STATE_PORT", "7475"))
TOKEN = os.environ.get("ZENDAYA_MOBILE_TOKEN", "").strip()


def main() -> int:
    if not TOKEN:
        print("ERROR: ZENDAYA_MOBILE_TOKEN is not set in your .env.")
        return 1
    if HOST in ("127.0.0.1", "localhost"):
        print("WARNING: ZENDAYA_BIND_HOST is localhost — the phone cannot reach it.")
        print("         Set it to your PC's Tailscale IP (tailscale ip -4) and restart.")
    payload = json.dumps({"host": HOST, "port": PORT, "token": TOKEN})
    print("\nPairing payload:\n  " + payload + "\n")
    try:
        import qrcode  # type: ignore
        qr = qrcode.QRCode(border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        print("(`pip install qrcode` to render a scannable QR here, or paste the")
        print(" payload above into any QR generator and scan it with the app.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
