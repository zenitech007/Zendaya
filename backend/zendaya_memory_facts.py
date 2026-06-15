"""
zendaya_memory_facts — durable structured facts.

Sits alongside the Chroma vector memory. Vector memory handles fuzzy semantic
recall of past conversation; this module handles crisp, persistent facts the
user explicitly told us or that the agent loop learned (e.g. "user prefers
tabs", "the project lives at C:\\foo", "API key is in env var BAR").

Storage: a single JSON file at <zendaya_logs>/facts.json. Schema:
    [{"text": str, "tags": [str, ...], "ts": float}, ...]

Public API:
    remember(fact, tags=None) -> str
    forget(matching) -> str
    recall(query, k=5) -> list[str]
    list_all(tag=None) -> list[str]
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import List, Optional


_LOGS_DIR = Path(__file__).resolve().parent.parent / "zendaya_logs"
_FACTS_PATH = _LOGS_DIR / "facts.json"


def _ensure_dir() -> None:
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _load() -> list:
    _ensure_dir()
    if not _FACTS_PATH.exists():
        return []
    try:
        with _FACTS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def _save(facts: list) -> None:
    _ensure_dir()
    tmp = _FACTS_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2, ensure_ascii=False)
    tmp.replace(_FACTS_PATH)


_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "i", "you", "he", "she", "it", "we", "they", "my", "your", "our",
    "to", "of", "in", "on", "at", "for", "with", "by", "from", "as",
    "and", "or", "but", "not", "no", "do", "does", "did", "have", "has",
    "had", "this", "that", "these", "those", "what", "when", "where",
    "why", "how", "can", "could", "would", "should", "will", "shall",
    "about", "into", "than", "so", "if", "because",
}


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS and len(t) > 1}


def remember(fact: str, tags: Optional[List[str]] = None) -> str:
    """Append a fact. Returns a short user-facing confirmation."""
    fact = (fact or "").strip()
    if not fact:
        return "I need a fact to remember."
    tags = [t.strip().lower() for t in (tags or []) if t and t.strip()]
    facts = _load()
    # Dedupe: if an existing fact has the same text (case-insensitive), refresh it.
    fact_lower = fact.lower()
    for entry in facts:
        if entry.get("text", "").lower() == fact_lower:
            entry["ts"] = time.time()
            existing_tags = set(entry.get("tags", []))
            existing_tags.update(tags)
            entry["tags"] = sorted(existing_tags)
            _save(facts)
            return f"Already knew that — refreshed it."
    facts.append({"text": fact, "tags": tags, "ts": time.time()})
    _save(facts)
    return f"Got it. I'll remember: {fact}"


def forget(matching: str) -> str:
    """Remove all facts whose text contains the substring (case-insensitive)."""
    needle = (matching or "").strip().lower()
    if not needle:
        return "Tell me what to forget."
    facts = _load()
    kept = [f for f in facts if needle not in f.get("text", "").lower()]
    removed = len(facts) - len(kept)
    if removed == 0:
        return f"I don't have any facts matching '{matching}'."
    _save(kept)
    return f"Forgot {removed} fact{'s' if removed != 1 else ''} matching '{matching}'."


def recall(query: str, k: int = 5) -> List[str]:
    """Return up to k facts most relevant to the query, by token overlap + recency."""
    facts = _load()
    if not facts:
        return []
    q_tokens = _tokens(query or "")
    if not q_tokens:
        # No useful query tokens — return the most recent facts.
        sorted_by_ts = sorted(facts, key=lambda f: f.get("ts", 0), reverse=True)
        return [f["text"] for f in sorted_by_ts[:k]]
    now = time.time()
    scored = []
    for f in facts:
        text = f.get("text", "")
        f_tokens = _tokens(text) | set(f.get("tags", []))
        overlap = len(q_tokens & f_tokens)
        if overlap == 0:
            continue
        # Recency boost: facts from the last 30 days get a small bump.
        age_days = max(0.0, (now - f.get("ts", now)) / 86400.0)
        recency = 1.0 / (1.0 + age_days / 30.0)
        score = overlap + 0.25 * recency
        scored.append((score, text))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [text for _, text in scored[:k]]


def list_all(tag: Optional[str] = None) -> List[str]:
    """Return all fact texts, optionally filtered to those carrying a given tag."""
    facts = _load()
    if tag:
        tag_lower = tag.strip().lower()
        return [f["text"] for f in facts if tag_lower in [t.lower() for t in f.get("tags", [])]]
    return [f.get("text", "") for f in facts]


def stats() -> str:
    facts = _load()
    return f"{len(facts)} facts at {_FACTS_PATH}"


if __name__ == "__main__":
    print(stats())
    print(remember("Test fact: the user likes tabs over spaces", tags=["preference", "formatting"]))
    print(recall("formatting tabs"))
