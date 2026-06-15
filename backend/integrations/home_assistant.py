"""
integrations.home_assistant.py
=========================
Home Assistant REST API integration. Handles real device control:
TVs, lights, locks, thermostats, switches, media players — anything HA exposes.

Set HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN in .env to activate.
"""

import os
import re
import time
import difflib
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import requests
from dotenv import load_dotenv

from memory.data_store import load as ds_load, save as ds_save

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

HA_URL = (os.getenv("HOME_ASSISTANT_URL") or "").rstrip("/")
HA_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN") or ""

_AVAIL_CACHE: Dict[str, Any] = {"checked_at": 0.0, "ok": False}
_AVAIL_TTL = 60.0  # seconds

_ENTITY_CACHE: Dict[str, Any] = {"loaded_at": 0.0, "entities": []}
_ENTITY_TTL = 300.0  # 5 minutes


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }


def ha_configured() -> bool:
    return bool(HA_URL and HA_TOKEN)


def ha_available() -> bool:
    """Return True if Home Assistant responds. Cached for 60s to avoid hammering."""
    if not ha_configured():
        return False
    now = time.time()
    if now - _AVAIL_CACHE["checked_at"] < _AVAIL_TTL:
        return _AVAIL_CACHE["ok"]
    try:
        r = requests.get(f"{HA_URL}/api/", headers=_headers(), timeout=4)
        ok = r.status_code == 200
    except Exception:
        ok = False
    _AVAIL_CACHE["checked_at"] = now
    _AVAIL_CACHE["ok"] = ok
    return ok


def ha_unavailable_message() -> str:
    if not ha_configured():
        return (
            "I'm not connected to Home Assistant yet. Add HOME_ASSISTANT_URL and "
            "HOME_ASSISTANT_TOKEN to your .env file (long-lived access token from "
            "your HA profile) and I'll take it from there."
        )
    return (
        f"I can't reach Home Assistant at {HA_URL} right now. Check that it's "
        "running and reachable from this machine."
    )


def ha_call_service(domain: str, service: str, entity_id: str, **data) -> Tuple[bool, str]:
    """POST /api/services/{domain}/{service}. Returns (success, message)."""
    if not ha_available():
        return False, ha_unavailable_message()
    url = f"{HA_URL}/api/services/{domain}/{service}"
    payload = {"entity_id": entity_id, **data}
    try:
        r = requests.post(url, headers=_headers(), json=payload, timeout=6)
        if r.status_code in (200, 201):
            return True, f"OK: {domain}.{service} on {entity_id}"
        return False, f"HA returned {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, f"HA call failed: {e}"


def ha_get_state(entity_id: str) -> Optional[Dict[str, Any]]:
    if not ha_available():
        return None
    try:
        r = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=_headers(), timeout=4)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def ha_list_entities(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """GET /api/states. Cached on disk + in memory."""
    now = time.time()
    if not force_refresh and _ENTITY_CACHE["entities"] and (now - _ENTITY_CACHE["loaded_at"] < _ENTITY_TTL):
        return _ENTITY_CACHE["entities"]

    cached = ds_load("ha_entities", default={})
    if not force_refresh and cached.get("entities") and (now - cached.get("saved_at", 0) < _ENTITY_TTL):
        _ENTITY_CACHE["entities"] = cached["entities"]
        _ENTITY_CACHE["loaded_at"] = now
        return cached["entities"]

    if not ha_available():
        return _ENTITY_CACHE["entities"] or cached.get("entities", [])

    try:
        r = requests.get(f"{HA_URL}/api/states", headers=_headers(), timeout=8)
        if r.status_code != 200:
            return _ENTITY_CACHE["entities"] or cached.get("entities", [])
        states = r.json()
        slim = [
            {
                "entity_id": s["entity_id"],
                "domain": s["entity_id"].split(".", 1)[0],
                "name": s.get("attributes", {}).get("friendly_name") or s["entity_id"],
                "state": s.get("state"),
            }
            for s in states
        ]
        _ENTITY_CACHE["entities"] = slim
        _ENTITY_CACHE["loaded_at"] = now
        ds_save("ha_entities", {"saved_at": now, "entities": slim})
        return slim
    except Exception:
        return _ENTITY_CACHE["entities"] or cached.get("entities", [])


def ha_resolve_entity(natural_name: str, domain_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fuzzy-match a user phrase ('living room tv', 'kitchen lights') to an entity."""
    natural = natural_name.lower().strip()

    aliases = ds_load("ha_aliases", default={})
    if natural in aliases:
        for ent in ha_list_entities():
            if ent["entity_id"] == aliases[natural]:
                return ent

    entities = ha_list_entities()
    if not entities:
        return None

    candidates = entities
    if domain_hint:
        candidates = [e for e in entities if e["domain"] == domain_hint] or entities

    name_to_ent = {e["name"].lower(): e for e in candidates}
    matches = difflib.get_close_matches(natural, name_to_ent.keys(), n=1, cutoff=0.55)
    if matches:
        return name_to_ent[matches[0]]

    for e in candidates:
        if natural in e["name"].lower() or natural in e["entity_id"].lower():
            return e

    tokens = natural.split()
    best, best_score = None, 0
    for e in candidates:
        ename = e["name"].lower()
        score = sum(1 for t in tokens if t in ename)
        if score > best_score:
            best, best_score = e, score
    if best and best_score >= max(1, len(tokens) // 2):
        return best
    return None


_DOMAIN_HINTS = {
    "light": "light",
    "lights": "light",
    "lamp": "light",
    "lamps": "light",
    "tv": "media_player",
    "television": "media_player",
    "speaker": "media_player",
    "music": "media_player",
    "lock": "lock",
    "door": "lock",
    "switch": "switch",
    "plug": "switch",
    "outlet": "switch",
    "thermostat": "climate",
    "ac": "climate",
    "heater": "climate",
    "fan": "fan",
}


def _detect_domain(text: str) -> Optional[str]:
    lt = text.lower()
    for word, domain in _DOMAIN_HINTS.items():
        if re.search(r"\b" + word + r"\b", lt):
            return domain
    return None


def ha_command(user_text: str) -> Optional[str]:
    """Parse a natural-language device command and execute via HA. Returns None if not a HA command."""
    lt = user_text.lower().strip()

    m_pct = re.search(
        r"\b(?:set|dim|brighten|change)\s+(?:the\s+)?(.+?)\s+(?:to\s+)?(\d{1,3})\s*(?:%|percent)?\s*$",
        lt,
    )
    m_onoff = re.search(
        r"\b(turn\s+(?:on|off)|switch\s+(?:on|off)|toggle)\s+(?:the\s+)?(.+?)\s*$",
        lt,
    )
    m_lock = re.search(r"\b(lock|unlock)\s+(?:the\s+)?(.+?)\s*$", lt)
    m_play = re.search(r"\b(play|pause|stop|resume)\s+(?:the\s+|on\s+(?:the\s+)?)?(.+?)\s*$", lt)
    m_list = re.search(r"\b(?:list|show|what)\s+(?:are\s+)?my\s+(?:smart\s+)?(?:devices|lights|switches|entities)\b", lt)
    m_rescan = re.search(r"\b(?:rescan|refresh|reload)\s+(?:my\s+)?(?:smart\s+home|home\s+assistant|devices)\b", lt)

    if m_list or m_rescan:
        if not ha_available():
            return ha_unavailable_message()
        ents = ha_list_entities(force_refresh=bool(m_rescan))
        if not ents:
            return "Home Assistant is reachable but has no entities exposed yet."
        controllable = [e for e in ents if e["domain"] in ("light", "switch", "lock", "media_player", "climate", "fan", "cover")]
        if not controllable:
            return f"I see {len(ents)} entities but none of the controllable types (lights, switches, locks, media, climate, fans, covers)."
        by_domain: Dict[str, List[str]] = {}
        for e in controllable:
            by_domain.setdefault(e["domain"], []).append(f"{e['name']} ({e['state']})")
        lines = [f"You have {len(controllable)} smart devices I can control:"]
        for domain, items in sorted(by_domain.items()):
            lines.append(f"  {domain}: {', '.join(items[:8])}{' ...' if len(items) > 8 else ''}")
        return "\n".join(lines)

    if m_pct:
        target_phrase, level_s = m_pct.group(1).strip(), m_pct.group(2)
        level = max(0, min(100, int(level_s)))
        if not ha_available():
            return ha_unavailable_message()
        domain_hint = _detect_domain(target_phrase) or "light"
        ent = ha_resolve_entity(target_phrase, domain_hint)
        if not ent:
            return f"I couldn't find a device called '{target_phrase}' in your Home Assistant."
        if ent["domain"] == "light":
            ok, msg = ha_call_service("light", "turn_on", ent["entity_id"], brightness_pct=level)
        elif ent["domain"] == "media_player":
            ok, msg = ha_call_service("media_player", "volume_set", ent["entity_id"], volume_level=level / 100.0)
        elif ent["domain"] == "climate":
            ok, msg = ha_call_service("climate", "set_temperature", ent["entity_id"], temperature=level)
        else:
            ok, msg = ha_call_service(ent["domain"], "turn_on", ent["entity_id"])
        return f"{ent['name']} set to {level}%." if ok else f"Couldn't set {ent['name']}: {msg}"

    if m_onoff:
        verb_phrase, target_phrase = m_onoff.group(1).strip(), m_onoff.group(2).strip()
        action = "toggle" if "toggle" in verb_phrase else ("turn_on" if "on" in verb_phrase else "turn_off")
        if not ha_available():
            return ha_unavailable_message()
        domain_hint = _detect_domain(target_phrase)
        ent = ha_resolve_entity(target_phrase, domain_hint)
        if not ent:
            return f"I couldn't find a device called '{target_phrase}' in your Home Assistant."
        domain = ent["domain"]
        if domain not in ("light", "switch", "media_player", "fan", "cover", "input_boolean", "automation", "script"):
            return f"I found '{ent['name']}' but I don't know how to {verb_phrase} a {domain}."
        ok, msg = ha_call_service(domain, action, ent["entity_id"])
        verb = "on" if action == "turn_on" else ("off" if action == "turn_off" else "toggled")
        return f"{ent['name']} {verb}." if ok else f"Couldn't {verb_phrase} {ent['name']}: {msg}"

    if m_lock:
        verb, target_phrase = m_lock.group(1).strip(), m_lock.group(2).strip()
        if not ha_available():
            return ha_unavailable_message()
        ent = ha_resolve_entity(target_phrase, "lock")
        if not ent or ent["domain"] != "lock":
            return f"I couldn't find a lock called '{target_phrase}'."
        ok, msg = ha_call_service("lock", "lock" if verb == "lock" else "unlock", ent["entity_id"])
        return f"{ent['name']} {'locked' if verb == 'lock' else 'unlocked'}." if ok else f"Couldn't {verb} {ent['name']}: {msg}"

    # Only claim media-player commands when the user names a specific HA device.
    # A bare "play music" should fall through to Spotify, not be hijacked by HA
    # just because the word "music" appeared.
    if m_play and re.search(r"\b(tv|television|speaker|player)\b", lt):
        verb, target_phrase = m_play.group(1).strip(), m_play.group(2).strip()
        if not ha_available():
            return ha_unavailable_message()
        ent = ha_resolve_entity(target_phrase, "media_player")
        if not ent:
            return f"I couldn't find a media player called '{target_phrase}'."
        service = {
            "play": "media_play",
            "resume": "media_play",
            "pause": "media_pause",
            "stop": "media_stop",
        }.get(verb, "media_play")
        ok, msg = ha_call_service("media_player", service, ent["entity_id"])
        return f"{verb.capitalize()}ed {ent['name']}." if ok else f"Couldn't {verb} {ent['name']}: {msg}"

    return None


def ha_alias(natural_name: str, entity_id: str) -> str:
    """Save a user-friendly alias for an entity ID."""
    aliases = ds_load("ha_aliases", default={})
    aliases[natural_name.lower().strip()] = entity_id
    ds_save("ha_aliases", aliases)
    return f"Saved alias: '{natural_name}' -> {entity_id}"
