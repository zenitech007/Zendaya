"""
Voice Debug Utility
-------------------
Standalone script to test Zendaya's voice output system.

Usage:
    poetry run python -m zendaya_backend.diagnostics.voice_debug
"""

import os
import pyttsx3
import requests
import tempfile

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

def test_offline_voice():
    print("🔊 Testing offline voice (Microsoft Zira)...")
    engine = pyttsx3.init()
    voices = engine.getProperty("voices")

    zira = next((v for v in voices if "ZIRA" in v.id.upper()), None)
    if zira:
        engine.setProperty("voice", zira.id)
        print(f"✅ Found voice: {zira.id}")
    else:
        print("⚠️ Zira voice not found, using system default")

    engine.say("Hello, I am Zendaya. This is a voice test. How do I sound?")
    engine.runAndWait()


def test_elevenlabs_voice():
    if not ELEVENLABS_API_KEY:
        print("⚠️ ELEVENLABS_API_KEY not set. Skipping ElevenLabs test.")
        return

    print("🎙️ Testing ElevenLabs API voice synthesis...")

    url = "https://api.elevenlabs.io/v1/text-to-speech/mxTlDrtKZzOqgjtBw4hM"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY,
    }
    payload = {"text": "Hello, I am Zendaya, powered by ElevenLabs."}

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"❌ ElevenLabs error {response.status_code}: {response.text}")
        return

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(response.content)
        temp_file = f.name

    print(f"✅ ElevenLabs voice test saved to: {temp_file}")

    try:
        os.startfile(temp_file)
    except Exception:
        print("⚠️ Could not auto-play audio. Open manually.")


if __name__ == "__main__":
    print("🎧 Running Zendaya voice system test...\n")
    test_offline_voice()
    test_elevenlabs_voice()
    print("\n✅ Voice debug completed.")
