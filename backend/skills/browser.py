"""
skills.browser — Playwright-driven browser automation.

A single shared browser session lives for the lifetime of the brain process.
Each call reuses the same context so cookies / login state persist within a
session. Public API is small and synchronous so the parser branch in zendaya.py
can call it like any other tool:

    open_url(url)            -> str   # navigate; returns page title + URL
    fill_field(selector, text) -> str # fill an input
    click(selector)          -> str   # click an element
    extract_text(selector)   -> str   # textContent of one element (or page)
    screenshot(name=None)    -> str   # write PNG into ~/Zendaya/screenshots/
    download_with_browser(url) -> str # full-page download for logged-in pages
    close_browser()          -> str   # tear down the shared session

Selectors accept Playwright's full syntax (CSS, text=, role=, xpath=).

Playwright is imported lazily — if the package isn't installed, every public
call returns a clear 'install playwright first' message instead of crashing.
"""

from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Optional, Tuple

_SCREENSHOT_DIR = Path(os.path.expanduser("~/Zendaya/screenshots"))
_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
_DOWNLOAD_DIR = Path(os.path.expanduser("~/Zendaya/downloads"))
_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

_LOCK = threading.Lock()
_STATE: dict = {"pw": None, "browser": None, "context": None, "page": None}


def _ensure_playwright() -> Tuple[Optional[Any], str]:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True, ""
    except Exception as e:
        return None, (
            "Playwright isn't installed. Run: "
            "`pip install playwright` then `python -m playwright install chromium`. "
            f"({e})"
        )


def _ensure_session():
    """Lazy-start a Chromium session. Returns (page, error_str)."""
    ok, err = _ensure_playwright()
    if not ok:
        return None, err
    if _STATE["page"] is not None:
        return _STATE["page"], ""
    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        _STATE.update(pw=pw, browser=browser, context=context, page=page)
        return page, ""
    except Exception as e:
        return None, f"Couldn't start Chromium: {e}"


def open_url(url: str) -> str:
    if not url or not re.match(r"^https?://", url, re.I):
        return "I need a full http(s):// URL."
    with _LOCK:
        page, err = _ensure_session()
        if err:
            return err
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title = page.title() or "(no title)"
            return f"Opened: {title} — {page.url}"
        except Exception as e:
            return f"Navigation failed: {e}"


def fill_field(selector: str, text: str) -> str:
    with _LOCK:
        page, err = _ensure_session()
        if err:
            return err
        try:
            page.fill(selector, text, timeout=10000)
            return f"Filled {selector}."
        except Exception as e:
            return f"Couldn't fill {selector}: {e}"


def click(selector: str) -> str:
    with _LOCK:
        page, err = _ensure_session()
        if err:
            return err
        try:
            page.click(selector, timeout=10000)
            return f"Clicked {selector}."
        except Exception as e:
            return f"Couldn't click {selector}: {e}"


def extract_text(selector: Optional[str] = None, max_chars: int = 4000) -> str:
    with _LOCK:
        page, err = _ensure_session()
        if err:
            return err
        try:
            if selector:
                text = page.text_content(selector, timeout=10000) or ""
            else:
                text = page.evaluate("document.body.innerText") or ""
            text = text.strip()
            if len(text) > max_chars:
                text = text[:max_chars] + "\n... (truncated)"
            return text or "(empty)"
        except Exception as e:
            return f"Couldn't read {selector or 'page'}: {e}"


def screenshot(name: Optional[str] = None) -> str:
    with _LOCK:
        page, err = _ensure_session()
        if err:
            return err
        safe = re.sub(r"[^A-Za-z0-9._\-]+", "_", name or f"shot-{int(time.time())}").strip("_")
        if not safe.lower().endswith(".png"):
            safe += ".png"
        out = _SCREENSHOT_DIR / safe
        try:
            page.screenshot(path=str(out), full_page=True)
            return f"Saved screenshot: {out}"
        except Exception as e:
            return f"Screenshot failed: {e}"


def download_with_browser(url: str) -> str:
    """Navigate and accept the resulting download into ~/Zendaya/downloads/."""
    with _LOCK:
        page, err = _ensure_session()
        if err:
            return err
        try:
            with page.expect_download(timeout=60000) as dl_info:
                page.goto(url)
            dl = dl_info.value
            dest = _DOWNLOAD_DIR / re.sub(r"[^A-Za-z0-9._\-]+", "_", dl.suggested_filename or "download.bin")
            dl.save_as(str(dest))
            return f"Downloaded: {dest}"
        except Exception as e:
            return f"Browser download failed: {e}"


def close_browser() -> str:
    with _LOCK:
        if _STATE["page"] is None:
            return "No browser session was open."
        try:
            _STATE["context"].close()
            _STATE["browser"].close()
            _STATE["pw"].stop()
        except Exception:
            pass
        _STATE.update(pw=None, browser=None, context=None, page=None)
        return "Browser session closed."
