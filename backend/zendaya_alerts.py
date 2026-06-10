"""
zendaya_alerts.py
=================
Proactive background alerts for Zendaya.
Runs on APScheduler in a daemon-friendly BackgroundScheduler.

Checks: battery, calendar events, unread emails, network devices.
Each alert fires only once per occurrence.
"""

import psutil
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

_send_response = None
_check_calendar_fn = None
_check_email_fn = None

_alerted = {
    "low_battery": False,
    "last_email_check": None,
    "last_email_subjects": set(),
    "calendar_alerted": set(),
    "known_interfaces": set(),
}


def _check_battery():
    try:
        batt = psutil.sensors_battery()
        if batt is None:
            return
        if batt.percent <= 20 and not batt.power_plugged:
            if not _alerted["low_battery"]:
                _alerted["low_battery"] = True
                if _send_response:
                    _send_response(
                        f"Warning: Battery at {batt.percent:.0f}%. Please plug in your charger."
                    )
        else:
            _alerted["low_battery"] = False
    except Exception:
        pass


def _check_upcoming_events():
    if not _check_calendar_fn:
        return
    try:
        from googleapiclient.errors import HttpError

        import zendaya as z
        service = z.get_google_service("calendar", "v3", z.CALENDAR_SCOPES)
        if not service:
            return

        now = datetime.now(timezone.utc)
        soon = now + timedelta(minutes=15)
        events_result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=soon.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        for event in events_result.get("items", []):
            eid = event.get("id", "")
            if eid in _alerted["calendar_alerted"]:
                continue
            summary = event.get("summary", "Unnamed event")
            start_str = event["start"].get("dateTime", event["start"].get("date"))
            start_dt = datetime.fromisoformat(start_str)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            mins_until = max(0, int((start_dt - now).total_seconds() / 60))
            _alerted["calendar_alerted"].add(eid)
            if _send_response:
                _send_response(
                    f"Heads up: '{summary}' starts in {mins_until} minutes."
                )

        stale = set()
        for eid in _alerted["calendar_alerted"]:
            found = any(e.get("id") == eid for e in events_result.get("items", []))
            if not found:
                stale.add(eid)
        _alerted["calendar_alerted"] -= stale

    except Exception:
        pass


def _check_new_emails():
    if not _check_email_fn:
        return
    try:
        import zendaya as z
        service = z.get_google_service("gmail", "v1", z.GMAIL_SCOPES)
        if not service:
            return

        results = service.users().messages().list(
            userId="me", labelIds=["INBOX", "UNREAD"], maxResults=5
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return

        current_ids = {m["id"] for m in messages}
        prev_ids = _alerted.get("last_email_subjects", set())

        new_ids = current_ids - prev_ids
        if not new_ids:
            return

        _alerted["last_email_subjects"] = current_ids

        if _alerted["last_email_check"] is None:
            _alerted["last_email_check"] = datetime.now()
            return

        msg_data = service.users().messages().get(
            userId="me", id=list(new_ids)[0]
        ).execute()
        headers = msg_data["payload"]["headers"]
        subject = next(
            (h["value"] for h in headers if h["name"] == "Subject"), "No subject"
        )
        sender = next(
            (h["value"] for h in headers if h["name"] == "From"), "Unknown sender"
        )
        sender = sender.split("<")[0].strip()

        _alerted["last_email_check"] = datetime.now()
        if _send_response:
            _send_response(
                f"You have {len(new_ids)} new unread email(s). "
                f"Most recent: {sender} — {subject}."
            )
    except Exception:
        pass


def _check_network():
    try:
        current = set(
            iface
            for iface, stats in psutil.net_if_stats().items()
            if stats.isup
        )
        if not _alerted["known_interfaces"]:
            _alerted["known_interfaces"] = current
            return

        new_ifaces = current - _alerted["known_interfaces"]
        if new_ifaces:
            _alerted["known_interfaces"] = current
            if _send_response:
                _send_response(
                    "Security alert: Unknown device detected on your network."
                )
    except Exception:
        pass


def start_alerts():
    import zendaya as z
    global _send_response, _check_calendar_fn, _check_email_fn
    _send_response = z.send_response
    _check_calendar_fn = z.check_calendar
    _check_email_fn = z.check_email

    _alerted["known_interfaces"] = set(
        iface for iface, stats in psutil.net_if_stats().items() if stats.isup
    )

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(_check_battery, "interval", minutes=5, id="battery_check")
    scheduler.add_job(_check_upcoming_events, "interval", minutes=10, id="calendar_check")
    scheduler.add_job(_check_new_emails, "interval", minutes=15, id="email_check")
    scheduler.add_job(_check_network, "interval", minutes=30, id="network_check")
    scheduler.start()
