"""
integrations.google_apis — thin wrapper around Google Calendar / Gmail APIs.

Used by skills.proactive to check upcoming calendar events.
Requires a valid Google OAuth `credentials.json` in the backend folder.
"""

from __future__ import annotations

import os
import datetime
from typing import Optional

# Re-use the auth helper from the main module when available.
try:
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    build = None  # type: ignore

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _get_calendar_service():
    """Return an authenticated Google Calendar service, or None."""
    if build is None:
        return None
    token_file = "token_calendar.json"
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, CALENDAR_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            if not os.path.exists("credentials.json"):
                return None
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", CALENDAR_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    try:
        return build("calendar", "v3", credentials=creds)
    except Exception:
        return None


def next_calendar_event() -> Optional[dict]:
    """Return the soonest upcoming calendar event as a dict, or None."""
    service = _get_calendar_service()
    if service is None:
        return None
    try:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=1,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = result.get("items", [])
        return events[0] if events else None
    except Exception:
        return None


def get_upcoming_events(max_results: int = 5) -> list[dict]:
    """Return a list of upcoming calendar events."""
    service = _get_calendar_service()
    if service is None:
        return []
    try:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return result.get("items", [])
    except Exception:
        return []
