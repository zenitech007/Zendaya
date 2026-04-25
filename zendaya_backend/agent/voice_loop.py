import asyncio
import os
from zendaya_backend.agent.zendaya_agent import ZendayaAgent
from zendaya_backend.knowledge.voice_service import VoiceService

from zendaya_backend.agent.tools.greeting import greet_user

class ZendayaVoiceLoop:
    def __init__(self, app_state):
        self.voice_service: VoiceService | None = getattr(app_state, "voice_service", None)

        self.agent = ZendayaAgent()
        self.running = False

    async def start(self):
        if not self.voice_service:
            print("Voice service unavailable.")
            return
        print("Zendaya voice loop active. Say 'Zendaya' to begin.")
        self.running = True

        while self.running:
            # record audio sample (replace with actual mic input later)
            audio_bytes = await self._listen_short()
            if not audio_bytes:
                await asyncio.sleep(0.5)
                continue

            # transcribe
            result = await self.voice_service.transcribe_with_context(audio_bytes)
            text = result.get("transcript", "").lower()
            if not text:
                continue

            # Reset idle timer and give main app a chance to interpret voice commands
            try:
                # local import to avoid circular imports at module import time
                from zendaya_backend.main import reset_idle_timer, process_voice_command
                try:
                    reset_idle_timer()
                except Exception:
                    pass
                cmd_response = await process_voice_command(text)
                if cmd_response:
                    # If it was a hologram/voice command, speak confirmation and skip chat
                    await self._respond(cmd_response)
                    continue
            except Exception:
                # If main isn't available or command processing fails, fall back
                pass

            if "zendaya" in text or "hey zendaya" in text:
                print(f"Heard wake word: {text}")
                await self._respond("Hello, how can I assist you today?")
                continue

            # --- Hologram Visibility Commands ---
            hologram = None
            try:
                from zendaya_backend.ui.hologram_desktop import get_hologram
                hologram = get_hologram()
            except Exception:
                pass

            if "hide yourself" in text:
                if hologram:
                    hologram.hide_hologram()
                continue
            elif "show yourself" in text:
                if hologram:
                    hologram.show_hologram()
                continue

            # ask the main agent
            response = await self.agent.process_text(text)
            if response:
                await self._respond(response)

    async def _listen_short(self):
        # placeholder — will use your mic recorder later
        return None

    async def _respond(self, text: str):
        print(f"Zendaya: {text}")
        if self.voice_service:
            await self.voice_service.synthesize_with_emotion(text, emotion="confident")
