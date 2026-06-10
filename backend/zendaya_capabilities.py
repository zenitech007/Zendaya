"""
zendaya_capabilities.py
=======================
Single source of truth for what Zendaya can actually do. Powers:
  - The honest answer to 'what can you do' (render_for_user)
  - The Gemini system prompt so the LLM stops hallucinating capabilities (render_for_llm)

Some sections are dynamic — they only appear when the underlying integration
is reachable (Home Assistant, KDE Connect).
"""

from typing import List, Tuple


def _ha_status():
    try:
        from zendaya_home_assistant import ha_available, ha_configured
        return ha_configured(), ha_available()
    except Exception:
        return False, False


def _kdec_status():
    try:
        from zendaya_phone import kdec_installed, kdec_available
        return kdec_installed(), kdec_available()
    except Exception:
        return False, False


def _spotify_status():
    try:
        from zendaya_spotify import spotify_configured, spotify_available
        return spotify_configured(), spotify_available()
    except Exception:
        return False, False


# Static capability sections. Format: (title, [bullet, ...])
_STATIC_SECTIONS: List[Tuple[str, List[str]]] = [
    ("System & apps", [
        "Open or close apps (Chrome, VS Code, Spotify, Notepad, Calculator, ...)",
        "Adjust volume and brightness, set them to a specific level",
        "Take screenshots, manage windows (focus, minimize, list, maximize)",
        "Shutdown, restart, sleep, lock the PC (always with confirmation)",
        "Type text or press hotkeys at the cursor",
        "Kill misbehaving processes",
    ]),
    ("Files & code", [
        "Create/rename/delete folders and files; move and copy them",
        "Generate code or content directly into a file (HTML, CSS, JS, Python, JSON, ...)",
        "Read, analyze, and edit existing files — automatic .bak backup before changes",
        "Find files by name; read clipboard, write clipboard",
    ]),
    ("Information & web", [
        "Web search via Tavily for up-to-date facts",
        "Check Gmail (unread summaries) and Google Calendar (next events)",
        "System status: CPU, memory, disk, battery",
        "Open any website in your default browser",
    ]),
    ("Wi-Fi & network", [
        "Show current Wi-Fi (SSID, signal, speed)",
        "List nearby Wi-Fi networks",
        "Connect to a saved network, disconnect, toggle the adapter (admin)",
        "Run a speed test",
    ]),
    ("Routines & alerts", [
        "Proactive alerts (low battery, calendar reminders, new emails)",
        "Set timed reminders ('remind me in 20 minutes to ...')",
        "Run named routines: 'run my good morning routine', 'run my bedtime routine', 'run my focus routine'",
        "Create your own: 'create a routine called X that does Y, then Z, then W'",
        "List or delete: 'list my routines', 'delete my X routine'",
    ]),
    ("Modes", [
        "Voice-only, text-only, or both",
        "Professional mode for formal tone",
    ]),
]


def _smart_home_section() -> Tuple[str, List[str]]:
    configured, reachable = _ha_status()
    if reachable:
        return ("Smart home (Home Assistant — connected)", [
            "Turn devices on/off ('turn off the bedroom light')",
            "Set levels ('set kitchen light to 30%', 'set thermostat to 22')",
            "Lock/unlock doors, play/pause/stop media players",
            "List your devices ('show me my smart devices')",
        ])
    if configured:
        return ("Smart home (Home Assistant — configured but unreachable)", [
            "I'll control your TVs/lights/locks/thermostats once HA is reachable.",
            "Check that Home Assistant is running and the URL/token in .env are correct.",
        ])
    return ("Smart home (not connected yet)", [
        "Set HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN in .env to enable real device control.",
        "Once connected: TVs, lights, locks, thermostats, switches, media players.",
    ])


def _phone_section() -> Tuple[str, List[str]]:
    installed, reachable = _kdec_status()
    if reachable:
        return ("Phone (KDE Connect — paired)", [
            "Ring/find my phone",
            "Send SMS to a saved contact ('text Mom on my way')",
            "Push text or files to your phone clipboard",
            "Share a file to your phone",
        ])
    if installed:
        return ("Phone (KDE Connect installed but no paired device)", [
            "Open KDE Connect on phone + PC and accept the pairing prompt.",
            "Then I can ring it, text contacts, push clipboard, share files.",
        ])
    return ("Phone (not connected yet)", [
        "Install KDE Connect on Windows and your Android phone.",
        "Pair them; I'll auto-detect the device and start handling phone tasks.",
    ])


def _spotify_section() -> Tuple[str, List[str]]:
    configured, reachable = _spotify_status()
    if reachable:
        return ("Music (Spotify Connect — connected)", [
            "Play a song, album, artist, or playlist ('play Blinding Lights on Spotify')",
            "Pause / resume / skip / previous track",
            "Set Spotify volume ('spotify volume 40')",
            "Now playing ('what's playing'), shuffle/repeat toggles",
            "List Spotify devices ('list my spotify devices')",
        ])
    if configured:
        return ("Music (Spotify configured but not authorized yet)", [
            "Run any spotify command — I'll open a browser for one-time login.",
            "Premium account required for play/pause/skip control.",
        ])
    return ("Music (Spotify not connected yet)", [
        "Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to .env to enable Spotify.",
        "Get them at developer.spotify.com/dashboard — free, takes 2 minutes.",
    ])


def _all_sections() -> List[Tuple[str, List[str]]]:
    sections = list(_STATIC_SECTIONS)
    sections.append(_smart_home_section())
    sections.append(_phone_section())
    sections.append(_spotify_section())
    return sections


def render_for_user() -> str:
    """Natural-language grouped list — speaks like Zendaya, not a manual."""
    out = ["Here's what I can actually do, grouped so you can pick what you want:"]
    for title, bullets in _all_sections():
        out.append("")
        out.append(f"{title}:")
        for b in bullets:
            out.append(f"  - {b}")
    out.append("")
    out.append("Ask me directly — no need for perfect phrasing. I'll figure it out.")
    return "\n".join(out)


def render_for_llm() -> str:
    """Compact bullet list for the Gemini system prompt."""
    parts = ["REAL CAPABILITIES (do not promise anything outside this list):"]
    for title, bullets in _all_sections():
        parts.append(f"- {title}: {'; '.join(bullets)}")
    return "\n".join(parts)
