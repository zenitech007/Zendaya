"""
skills.languages.py
====================
Language registry + sticky preference + parser for switch commands.

One source of truth for:
  - Whisper language code (passed to model.transcribe)
  - Gemini system-prompt hint (so replies are in the right language)
  - ElevenLabs model selection (multilingual vs English-fast)

The current language is held in a module-level variable. zendaya.py syncs
it with MEM["language"] on startup and on every change so it persists.
"""

import re
from typing import Optional, Tuple

# Per-language ElevenLabs voice IDs. None means "use the default Zendaya voice".
# Add a voice fingerprint here when you've trained/picked one for that language.
LANGUAGES = {
    "english": {
        "whisper": "en",
        "gemini_hint": "English",
        "is_pidgin": False,
        "switched_msg": "Got it — I'll speak English now.",
        "voice_id": None,
    },
    "yoruba": {
        "whisper": "yo",
        "gemini_hint": "Yoruba",
        "is_pidgin": False,
        "switched_msg": "Ó dáa — màá sọ Yorùbá láti ìsinsìnyí.",
        "voice_id": "eOHsvebhdtt0XFeHVMQY",
    },
    "igbo": {
        "whisper": "ig",
        "gemini_hint": "Igbo",
        "is_pidgin": False,
        "switched_msg": "Ọ dị mma — aga m asụ Igbo ugbu a.",
        "voice_id": None,
    },
    "hausa": {
        "whisper": "ha",
        "gemini_hint": "Hausa",
        "is_pidgin": False,
        "switched_msg": "To, zan yi magana da Hausa daga yanzu.",
        "voice_id": None,
    },
    "pidgin": {
        # Whisper has no Pidgin code; English transcription is the closest fit.
        "whisper": "en",
        "gemini_hint": "Nigerian Pidgin English",
        "is_pidgin": True,
        "switched_msg": "Oya, na Pidgin we go dey speak from now.",
        "voice_id": None,
    },
}

DEFAULT = "english"
_current = DEFAULT


# Regex aliases per language, matched against natural-language switch commands.
_ALIASES = {
    "english": [r"english", r"\b英語\b"],
    "yoruba":  [r"yoruba", r"yor[uúù]b[áa]"],
    "igbo":    [r"igbo", r"ibo"],
    "hausa":   [r"hausa", r"hawsa"],
    "pidgin":  [r"pidgin", r"pigin", r"naija(?:\s+language)?", r"broken\s+english"],
}

_SWITCH_VERBS = (
    r"(?:speak|talk|reply|respond|answer|switch|change|go|"
    r"set\s+language\s+to|use|"
    r"sọ|wa|fọ̀|sọ̀rọ̀\s+ní|"
    r"yi|ekwu|kwuo\s+na|"
    r"yi\s+magana\s+(?:da|cikin)|"
    r"back\s+to|return\s+to)"
)


def current() -> dict:
    """Return the active language dict (whisper code, gemini_hint, etc)."""
    return LANGUAGES[_current]


def current_name() -> str:
    return _current


def set_current(name: str) -> Optional[dict]:
    """Set the active language by canonical name. Returns the new lang dict, or None if unknown."""
    global _current
    name = name.lower().strip()
    if name not in LANGUAGES:
        return None
    _current = name
    return LANGUAGES[name]


def is_supported(name: str) -> bool:
    return name.lower().strip() in LANGUAGES


def voice_id_for(name: Optional[str] = None) -> Optional[str]:
    """ElevenLabs voice ID for the given (or current) language. None = caller should use default."""
    n = (name or _current).lower().strip()
    info = LANGUAGES.get(n)
    if not info:
        return None
    return info.get("voice_id")


def parse_language_command(text: str) -> Optional[Tuple[str, str]]:
    """
    Detect 'switch language' intents.

    Returns (canonical_name, switched_msg) on match, else None.

    Matches phrases like:
      "speak Yoruba", "switch to Hausa", "respond in Igbo",
      "back to English", "use Pidgin", "talk Naija",
      "sọ Yorùbá", "yi magana da Hausa".
    """
    if not text:
        return None
    low = text.lower()

    # Standalone form: "Yoruba mode", "in Yoruba" etc — but only if a verb is nearby.
    # We require at least one of: a switch verb OR an "in <lang>" preposition,
    # so plain mentions like "what does yoruba mean" don't trigger.
    has_verb = re.search(_SWITCH_VERBS, low) is not None
    has_in = re.search(r"\b(?:in|ni|na|cikin|da)\s+\w", low) is not None
    if not (has_verb or has_in):
        return None

    for canonical, patterns in _ALIASES.items():
        for pat in patterns:
            if re.search(rf"\b{pat}\b", low):
                return canonical, LANGUAGES[canonical]["switched_msg"]
    return None


def language_directive(lang_name: Optional[str] = None) -> str:
    """Text to splice into Gemini's system prompt for the current (or given) language."""
    name = (lang_name or _current).lower()
    info = LANGUAGES.get(name, LANGUAGES[DEFAULT])
    base = f"Reply in {info['gemini_hint']}. Do not include English translations or transliterations unless explicitly asked."
    if info["is_pidgin"]:
        base += (
            " Use authentic Nigerian Pidgin orthography (e.g. 'wetin', 'dey', 'sabi', 'abeg'). "
            "Do not write standard English; do not add italics, footnotes, or English subtitles."
        )
    elif name != DEFAULT:
        base += " Use proper diacritics where applicable (e.g. tone marks for Yoruba)."
    return base


if __name__ == "__main__":
    tests = [
        "speak Yoruba",
        "switch to hausa please",
        "respond in Igbo from now on",
        "back to English",
        "use pidgin",
        "talk Naija",
        "what does Yoruba mean?",   # should NOT trigger
        "sọ Yorùbá",
        "yi magana da hausa",
    ]
    for t in tests:
        print(f"{t!r:50} -> {parse_language_command(t)}")
