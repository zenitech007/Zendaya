import pyttsx3
from zendaya_backend.utils.network_check import is_connected

def speak_message(message: str, elevenlabs_client=None, voice_id=None):
    """
    Smart speech function.
    - Uses ElevenLabs if online
    - Falls back to pyttsx3 offline voice
    """
    if is_connected() and elevenlabs_client:
        try:
            # ✅ Online: Use ElevenLabs TTS
            print("🎙️ Using ElevenLabs voice (online mode)...")
            audio = elevenlabs_client.generate(
                text=message,
                voice=voice_id or "Bella",
                model="eleven_multilingual_v2"
            )
            elevenlabs_client.play(audio)
            return
        except Exception as e:
            print(f"⚠️ ElevenLabs voice failed: {e}, switching to offline voice...")

    # 💻 Offline: Fallback to pyttsx3
    print("🗣️ Using pyttsx3 voice (offline mode)...")
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        selected_voice = next((v.id for v in voices if "Zira" in v.name or "Female" in v.name), voices[0].id)
        engine.setProperty('voice', selected_voice)
        engine.setProperty('rate', 170)
        engine.setProperty('volume', 1.0)
        engine.say(message)
        engine.runAndWait()
    except Exception as e:
        print(f"(Offline voice skipped: {e})")
