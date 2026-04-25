import asyncio
from zendaya_backend.knowledge.voice_service import VoiceService
from TTS.api import TTS

# Monkey-patch VoiceService to enable download progress for testing
original_init = VoiceService.__init__

def new_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    # Enable progress bar and verbose for TTS
    if hasattr(self, 'tts'):
        self.tts.progress_bar = True
        self.tts.verbose = True

VoiceService.__init__ = new_init

async def test():
    vs = VoiceService()
    res = await vs.synthesize(
        "The heart of Wakanda beats strong — with unity, and with purpose.", 
        emotion="calm"
    )
    if res:
        await vs.play(res["path"])

asyncio.run(test())
