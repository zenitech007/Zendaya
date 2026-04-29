"""
zendaya_system_access.py
========================
Full laptop system access module for Zendaya.
Drop this file into your backend/ folder, then add this line
at the top of zendaya.py (after the other imports):

    from zendaya_system_access import *

Then add these lines inside handle_user_command(), BEFORE the
final gemini_reply fallback (after the existing sysc block):

    sys_result = handle_system_access(user_text)
    if sys_result is not None:
        send_response(sys_result)
        return

Required installs (run once):
    pip install pyautogui pillow psutil pygetwindow pywin32 smtplib
    (psutil and pygetwindow already installed from requirements)

For Gmail sending: set these in your .env file:
    GMAIL_SENDER=your.email@gmail.com
    GMAIL_APP_PASSWORD=your-16-char-app-password
    (Generate app password at: myaccount.google.com/apppasswords)
"""

import os
import re
import shutil
import platform
import subprocess
import smtplib
import ssl
import threading
import time
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

import psutil

# Optional imports — degrade gracefully if not installed
try:
    import pyautogui
    pyautogui.FAILSAFE = True   # move mouse to top-left corner to abort
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pygetwindow as gw
    _PYGETWINDOW = True
except ImportError:
    _PYGETWINDOW = False

# ─────────────────────────────────────────────
# 1.  FOLDER & FILE MANAGEMENT
# ─────────────────────────────────────────────

def create_folder(path: str) -> str:
    """Create a folder (and any missing parents)."""
    try:
        expanded = os.path.expandvars(os.path.expanduser(path))
        os.makedirs(expanded, exist_ok=True)
        return f"Folder created: {expanded}"
    except Exception as e:
        return f"Couldn't create folder: {e}"


def create_file(filepath: str) -> str:
    """Create an empty file. Parent directories are created if needed."""
    try:
        expanded = os.path.expandvars(os.path.expanduser(filepath))
        parent = os.path.dirname(expanded)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if os.path.exists(expanded):
            return f"File already exists: {expanded}"
        with open(expanded, "w", encoding="utf-8") as f:
            pass
        return f"File created: {expanded}"
    except Exception as e:
        return f"Couldn't create file: {e}"


def rename_item(source: str, new_name: str) -> str:
    """Rename a file or folder."""
    try:
        src = Path(os.path.expandvars(os.path.expanduser(source)))
        dst = src.parent / new_name
        src.rename(dst)
        return f"Renamed to '{new_name}'."
    except Exception as e:
        return f"Rename failed: {e}"


def list_folder(path: str = "~") -> str:
    """List contents of a folder."""
    try:
        expanded = os.path.expanduser(path)
        items = os.listdir(expanded)
        if not items:
            return f"'{expanded}' is empty."
        dirs  = [f"📁 {i}" for i in items if os.path.isdir(os.path.join(expanded, i))]
        files = [f"📄 {i}" for i in items if os.path.isfile(os.path.join(expanded, i))]
        result = dirs + files
        return f"Contents of {expanded}:\n" + "\n".join(result[:40])
    except Exception as e:
        return f"Could not list folder: {e}"


def open_folder_in_explorer(path: str) -> str:
    """Open a folder in Windows Explorer / Finder / Nautilus."""
    try:
        expanded = os.path.expandvars(os.path.expanduser(path))
        if platform.system() == "Windows":
            os.startfile(expanded)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", expanded])
        else:
            subprocess.Popen(["xdg-open", expanded])
        return f"Opened '{expanded}' in file manager."
    except Exception as e:
        return f"Could not open folder: {e}"


# ─────────────────────────────────────────────
# 2.  EMAIL (Gmail via App Password)
# ─────────────────────────────────────────────

def send_email(to: str, subject: str, body: str) -> str:
    """Send an email via Gmail SMTP using an App Password."""
    sender  = os.getenv("GMAIL_SENDER", "")
    app_pwd = os.getenv("GMAIL_APP_PASSWORD", "")

    if not sender or not app_pwd:
        return (
            "I can't send email yet. Add these to your .env file:\n"
            "  GMAIL_SENDER=your.email@gmail.com\n"
            "  GMAIL_APP_PASSWORD=your-16-char-app-password\n"
            "Generate an app password at: myaccount.google.com/apppasswords"
        )

    try:
        msg = MIMEMultipart()
        msg["From"]    = sender
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
            server.login(sender, app_pwd)
            server.sendmail(sender, to, msg.as_string())
        return f"Email sent to {to} with subject '{subject}'."
    except Exception as e:
        return f"Failed to send email: {e}"


# ─────────────────────────────────────────────
# 3.  VOLUME CONTROL
# ─────────────────────────────────────────────

def set_volume(level: int) -> str:
    """Set system volume 0–100."""
    level = max(0, min(100, level))
    try:
        if platform.system() == "Windows":
            # Uses built-in nircmd if available, otherwise PowerShell
            ps = (
                f"$obj = New-Object -ComObject WScript.Shell; "
                f"1..50 | ForEach-Object {{ $obj.SendKeys([char]174) }}; "   # mute first
                f"$vol = [math]::Round({level} / 2); "
                f"1..$vol | ForEach-Object {{ $obj.SendKeys([char]175) }}"
            )
            # Better approach via pycaw or nircmd, fallback to PowerShell
            subprocess.run(
                ["powershell", "-Command",
                 f"(New-Object -ComObject WScript.Shell).SendKeys([char]174)"],
                capture_output=True
            )
            if _PYAUTOGUI:
                # Use pyautogui volume keys
                import pyautogui
                for _ in range(50):
                    pyautogui.press("volumedown")
                steps = round(level / 2)
                for _ in range(steps):
                    pyautogui.press("volumeup")
                return f"Volume set to approximately {level}%."
        elif platform.system() == "Darwin":
            subprocess.run(["osascript", "-e", f"set volume output volume {level}"])
            return f"Volume set to {level}%."
        else:
            subprocess.run(["amixer", "-q", "sset", "Master", f"{level}%"])
            return f"Volume set to {level}%."
    except Exception as e:
        return f"Volume control failed: {e}"


def mute_volume() -> str:
    """Mute system audio."""
    try:
        if platform.system() == "Windows" and _PYAUTOGUI:
            pyautogui.press("volumemute")
            return "Audio muted."
        elif platform.system() == "Darwin":
            subprocess.run(["osascript", "-e", "set volume with output muted"])
            return "Audio muted."
        else:
            subprocess.run(["amixer", "-q", "sset", "Master", "mute"])
            return "Audio muted."
    except Exception as e:
        return f"Mute failed: {e}"


def unmute_volume() -> str:
    """Unmute system audio."""
    try:
        if platform.system() == "Windows" and _PYAUTOGUI:
            pyautogui.press("volumemute")
            return "Audio unmuted."
        elif platform.system() == "Darwin":
            subprocess.run(["osascript", "-e", "set volume without output muted"])
            return "Audio unmuted."
        else:
            subprocess.run(["amixer", "-q", "sset", "Master", "unmute"])
            return "Audio unmuted."
    except Exception as e:
        return f"Unmute failed: {e}"


def adjust_volume(direction: str, steps: int = 5) -> str:
    """Increase or decrease volume by N steps (~10% per 5 steps)."""
    try:
        if platform.system() == "Windows" and _PYAUTOGUI:
            key = "volumeup" if direction == "up" else "volumedown"
            for _ in range(steps):
                pyautogui.press(key)
            word = "Increased" if direction == "up" else "Decreased"
            return f"{word} volume by {steps * 2}%."
        elif platform.system() == "Darwin":
            current = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"],
                                     capture_output=True, text=True).stdout.strip()
            try:
                cur = int(current)
            except ValueError:
                cur = 50
            delta = steps * 2
            new_vol = max(0, min(100, cur + delta if direction == "up" else cur - delta))
            subprocess.run(["osascript", "-e", f"set volume output volume {new_vol}"])
            return f"Volume set to {new_vol}%."
        else:
            sign = f"+{steps * 2}" if direction == "up" else f"-{steps * 2}"
            subprocess.run(["amixer", "-q", "sset", "Master", f"{sign}%"])
            return f"Volume adjusted {direction}."
    except Exception as e:
        return f"Volume adjustment failed: {e}"


# ─────────────────────────────────────────────
# 3b. BRIGHTNESS CONTROL
# ─────────────────────────────────────────────

def set_brightness(level: int) -> str:
    """Set screen brightness 0–100."""
    level = max(0, min(100, level))
    try:
        if platform.system() == "Windows":
            ps_cmd = (
                f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
                f".WmiSetBrightness(1, {level})"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, creationflags=0x08000000
            )
            if result.returncode == 0:
                return f"Brightness set to {level}%."
            return f"Brightness command ran but may not have worked on this display: {result.stderr.strip()}"
        elif platform.system() == "Darwin":
            subprocess.run(["brightness", str(level / 100)])
            return f"Brightness set to {level}%."
        else:
            subprocess.run(["xrandr", "--output", "eDP-1", "--brightness", str(level / 100)])
            return f"Brightness set to {level}%."
    except Exception as e:
        return f"Brightness control failed: {e}"


def adjust_brightness(direction: str, amount: int = 10) -> str:
    """Increase or decrease brightness by a percentage."""
    try:
        if platform.system() == "Windows":
            get_cmd = (
                "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness)"
                ".CurrentBrightness"
            )
            result = subprocess.run(
                ["powershell", "-Command", get_cmd],
                capture_output=True, text=True, creationflags=0x08000000
            )
            try:
                current = int(result.stdout.strip())
            except ValueError:
                current = 50
            new_level = max(0, min(100, current + amount if direction == "up" else current - amount))
            return set_brightness(new_level)
        else:
            new_level = 50 + amount if direction == "up" else 50 - amount
            return set_brightness(max(0, min(100, new_level)))
    except Exception as e:
        return f"Brightness adjustment failed: {e}"


# ─────────────────────────────────────────────
# 3c. WALLPAPER
# ─────────────────────────────────────────────

def set_wallpaper(image_path: str) -> str:
    """Set the desktop wallpaper to a given image file."""
    try:
        expanded = os.path.expandvars(os.path.expanduser(image_path))
        if not os.path.isfile(expanded):
            return f"I can't find the image file: {expanded}"
        if platform.system() == "Windows":
            import ctypes
            SPI_SETDESKWALLPAPER = 0x0014
            result = ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER, 0, expanded, 3
            )
            if result:
                return f"Wallpaper changed to '{os.path.basename(expanded)}'."
            return "Wallpaper change command was sent but may not have taken effect."
        elif platform.system() == "Darwin":
            subprocess.run(["osascript", "-e",
                            f'tell application "Finder" to set desktop picture to POSIX file "{expanded}"'])
            return f"Wallpaper changed to '{os.path.basename(expanded)}'."
        else:
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri",
                            f"file://{expanded}"])
            return f"Wallpaper changed to '{os.path.basename(expanded)}'."
    except Exception as e:
        return f"Wallpaper change failed: {e}"


def open_wallpaper_settings() -> str:
    """Open the OS wallpaper/personalization settings."""
    try:
        if platform.system() == "Windows":
            os.startfile("ms-settings:personalization-background")
            return "Opening wallpaper settings."
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-a", "System Preferences"])
            return "Opening System Preferences — navigate to Desktop & Screen Saver."
        else:
            subprocess.Popen(["xdg-open", "gnome-control-center", "background"])
            return "Opening background settings."
    except Exception as e:
        return f"Couldn't open wallpaper settings: {e}"


# ─────────────────────────────────────────────
# 4.  SCREENSHOT
# ─────────────────────────────────────────────

def take_screenshot(filename: str = None) -> str:
    """Take a screenshot and save it to the Desktop."""
    if not _PYAUTOGUI:
        return "Screenshot requires pyautogui. Run: pip install pyautogui pillow"
    try:
        desktop = Path.home() / "Desktop"
        desktop.mkdir(exist_ok=True)
        name = filename or f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = desktop / name
        pyautogui.screenshot(str(path))
        return f"Screenshot saved to Desktop as '{name}'."
    except Exception as e:
        return f"Screenshot failed: {e}"


# ─────────────────────────────────────────────
# 5.  TYPING & KEYBOARD
# ─────────────────────────────────────────────

def type_text(text: str, delay: float = 0.05) -> str:
    """Type text at the current cursor position."""
    if not _PYAUTOGUI:
        return "Typing requires pyautogui. Run: pip install pyautogui"
    try:
        time.sleep(1.5)  # Give user time to click into target app
        pyautogui.typewrite(text, interval=delay)
        return f"Typed: {text}"
    except Exception as e:
        return f"Typing failed: {e}"


def press_key(key: str) -> str:
    """Press a keyboard key (e.g. enter, esc, f5, ctrl+c)."""
    if not _PYAUTOGUI:
        return "Key press requires pyautogui. Run: pip install pyautogui"
    try:
        if "+" in key:
            keys = [k.strip() for k in key.split("+")]
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(key.strip())
        return f"Pressed: {key}"
    except Exception as e:
        return f"Key press failed: {e}"


# ─────────────────────────────────────────────
# 6.  WINDOW MANAGEMENT
# ─────────────────────────────────────────────

def list_open_windows() -> str:
    """List all currently open windows."""
    if not _PYGETWINDOW:
        return "Window listing requires pygetwindow. Run: pip install pygetwindow"
    try:
        wins = [w.title for w in gw.getAllWindows() if w.title.strip()]
        if not wins:
            return "No open windows found."
        return "Open windows:\n" + "\n".join(f"• {w}" for w in wins[:20])
    except Exception as e:
        return f"Could not list windows: {e}"


def focus_window(title: str) -> str:
    """Bring a window to the foreground by partial title match."""
    if not _PYGETWINDOW:
        return "Window control requires pygetwindow."
    try:
        matches = gw.getWindowsWithTitle(title)
        if not matches:
            return f"No window found matching '{title}'."
        matches[0].activate()
        return f"Focused: {matches[0].title}"
    except Exception as e:
        return f"Could not focus window: {e}"


def minimize_window(title: str) -> str:
    """Minimize a window by partial title match."""
    if not _PYGETWINDOW:
        return "Window control requires pygetwindow."
    try:
        matches = gw.getWindowsWithTitle(title)
        if not matches:
            return f"No window found matching '{title}'."
        matches[0].minimize()
        return f"Minimized: {matches[0].title}"
    except Exception as e:
        return f"Could not minimize: {e}"


def maximize_window(title: str) -> str:
    """Maximize a window by partial title match."""
    if not _PYGETWINDOW:
        return "Window control requires pygetwindow."
    try:
        matches = gw.getWindowsWithTitle(title)
        if not matches:
            return f"No window found matching '{title}'."
        matches[0].maximize()
        return f"Maximized: {matches[0].title}"
    except Exception as e:
        return f"Could not maximize: {e}"


# ─────────────────────────────────────────────
# 7.  PROCESS MANAGEMENT
# ─────────────────────────────────────────────

def list_running_processes(filter_name: str = "") -> str:
    """List running processes, optionally filtered by name."""
    try:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                if filter_name.lower() in p.info["name"].lower():
                    procs.append(
                        f"[{p.info['pid']}] {p.info['name']} "
                        f"CPU:{p.info['cpu_percent']:.1f}% MEM:{p.info['memory_percent']:.1f}%"
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if not procs:
            return f"No processes found matching '{filter_name}'." if filter_name else "No processes found."
        return "\n".join(procs[:25])
    except Exception as e:
        return f"Process list failed: {e}"


def kill_process_by_name(name: str) -> str:
    """Kill all processes matching a name."""
    killed = []
    try:
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if name.lower() in p.info["name"].lower():
                    p.kill()
                    killed.append(p.info["name"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed:
            return f"Killed: {', '.join(set(killed))}"
        return f"No process named '{name}' was running."
    except Exception as e:
        return f"Kill failed: {e}"


# ─────────────────────────────────────────────
# 8.  BATTERY & POWER INFO
# ─────────────────────────────────────────────

def get_battery_status() -> str:
    """Get current battery level and charging status."""
    try:
        batt = psutil.sensors_battery()
        if batt is None:
            return "No battery detected — this might be a desktop."
        status = "charging" if batt.power_plugged else "on battery"
        remaining = ""
        if batt.secsleft != psutil.POWER_TIME_UNLIMITED and batt.secsleft > 0:
            mins = batt.secsleft // 60
            remaining = f", about {mins} minutes remaining"
        return f"Battery at {batt.percent:.0f}% — {status}{remaining}."
    except Exception as e:
        return f"Battery info failed: {e}"


# ─────────────────────────────────────────────
# 9.  WIFI / NETWORK INFO
# ─────────────────────────────────────────────

def get_network_info() -> str:
    """Get current IP addresses and connection info."""
    try:
        lines = []
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        for iface, addr_list in addrs.items():
            is_up = stats.get(iface) and stats[iface].isup
            if not is_up:
                continue
            for addr in addr_list:
                if addr.family.name in ("AF_INET", "AF_INET6"):
                    lines.append(f"{iface}: {addr.address}")
        if not lines:
            return "No active network connections found."
        return "Network interfaces:\n" + "\n".join(lines)
    except Exception as e:
        return f"Network info failed: {e}"


# ─────────────────────────────────────────────
# 10.  DISK USAGE
# ─────────────────────────────────────────────

def get_disk_usage(path: str = "/") -> str:
    """Get disk usage for a drive/path."""
    try:
        if platform.system() == "Windows":
            path = "C:\\"
        usage = psutil.disk_usage(path)
        pct = usage.percent
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        return (
            f"Disk usage on {path}: {pct:.1f}% used. "
            f"{free_gb:.1f} GB free of {total_gb:.1f} GB total."
        )
    except Exception as e:
        return f"Disk info failed: {e}"


# ─────────────────────────────────────────────
# 11.  SET REMINDER (local, terminal popup)
# ─────────────────────────────────────────────

def set_reminder(message: str, minutes: float) -> str:
    """Set a reminder that will pop up after N minutes."""
    def _remind():
        time.sleep(minutes * 60)
        print(f"\n⏰ REMINDER: {message}\n")
        if platform.system() == "Windows":
            try:
                subprocess.run(
                    ["powershell", "-Command",
                     f'Add-Type -AssemblyName System.Windows.Forms; '
                     f'[System.Windows.Forms.MessageBox]::Show("{message}", "Zendaya Reminder")'],
                    capture_output=True
                )
            except Exception:
                pass

    t = threading.Thread(target=_remind, daemon=True)
    t.start()
    return f"Reminder set! I'll alert you in {minutes:.0f} minute(s): '{message}'"


# ─────────────────────────────────────────────
# 12.  OPEN URL / WEBSITE
# ─────────────────────────────────────────────

def open_website(url: str) -> str:
    """Open a URL in the default browser."""
    import webbrowser
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opening {url} in your browser."


# ─────────────────────────────────────────────
# 13.  CLIPBOARD (extended)
# ─────────────────────────────────────────────

def get_clipboard() -> str:
    """Read text from clipboard."""
    try:
        import pyperclip
        text = pyperclip.paste()
        return f"Clipboard contains: {text[:500]}" if text else "Clipboard is empty."
    except Exception as e:
        return f"Clipboard read failed: {e}"


def set_clipboard(text: str) -> str:
    """Write text to clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return "Text copied to clipboard."
    except Exception as e:
        return f"Clipboard write failed: {e}"


# ─────────────────────────────────────────────
# COMMAND PARSER — maps natural language → functions
# ─────────────────────────────────────────────

def handle_system_access(user_text: str) -> Optional[str]:
    """
    Call this from handle_user_command() BEFORE the gemini_reply fallback.
    Returns a response string if a command was matched, or None to fall through.
    """
    lt = user_text.lower().strip()
    original = user_text.strip()

    # ── FOLDER CREATION (specific: name provided) ──
    m = re.match(r"(?:zendaya,?\s*)?(?:create|make|new)\s+(?:a\s+)?(?:new\s+)?folder\s+(?:called\s+|named\s+)?['\"]?(.+?)['\"]?(?:\s+(?:in|on|at)\s+(.+))?$", lt)
    if m:
        name = m.group(1).strip()
        if name in ("on", "in", "at", "please", "now", "for me"):
            return "__ask_folder_name__"
        location = m.group(2).strip() if m.group(2) else "~"
        full_path = os.path.join(os.path.expanduser(location), name)
        return create_folder(full_path)

    # ── FOLDER CREATION (vague: no name provided) ──
    if re.match(r"(?:zendaya,?\s*)?(?:create|make|new)\s+(?:a\s+)?(?:new\s+)?folder\s*$", lt):
        return "__ask_folder_name__"

    # ── FILE / DOCUMENT CREATION ──
    _file_location_shortcuts = {
        "desktop": os.path.join(os.path.expanduser("~"), "Desktop"),
        "documents": os.path.join(os.path.expanduser("~"), "Documents"),
        "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
        "home": os.path.expanduser("~"),
    }
    _file_type_words = r"(?:text\s+)?(?:file|document|text\s*(?:file|document)?|script|note)"

    # Vague: "create a file" / "create a text document" (no name, no location)
    if re.match(
        r"(?:zendaya,?\s*)?(?:create|make|new)\s+(?:a\s+)?(?:new\s+)?"
        + _file_type_words + r"\s*$",
        lt
    ):
        return "__ask_file_name__"

    # Vague with location: "create a file in the folder" / "create a document in documents"
    m = re.match(
        r"(?:zendaya,?\s*)?(?:create|make|new)\s+(?:a\s+)?(?:new\s+)?"
        + _file_type_words +
        r"\s+(?:in|on|at|inside)\s+(.+)$",
        lt
    )
    if m:
        return "__ask_file_name__"

    # Specific: "create file called readme in documents"
    m = re.match(
        r"(?:zendaya,?\s*)?(?:create|make|new)\s+(?:a\s+)?(?:new\s+)?"
        + _file_type_words +
        r"\s+(?:called\s+|named\s+)['\"]?(.+?)['\"]?"
        r"(?:\s+(?:in|on|at|inside)\s+(.+))?$",
        lt
    )
    if m:
        name = m.group(1).strip()
        if "." not in name:
            name += ".txt"
        location = m.group(2).strip().strip('"').strip("'") if m.group(2) else None
        if location:
            location = _file_location_shortcuts.get(location.lower(), os.path.expanduser(location))
            full_path = os.path.join(location, name)
        else:
            full_path = name
        return create_file(full_path)

    # Specific with name directly: "create file readme.txt in downloads"
    m = re.match(
        r"(?:zendaya,?\s*)?(?:create|make|new)\s+(?:a\s+)?(?:new\s+)?"
        + _file_type_words +
        r"\s+['\"]?(\S+\.\S+)['\"]?"
        r"(?:\s+(?:in|on|at|inside)\s+(.+))?$",
        lt
    )
    if m:
        name = m.group(1).strip()
        location = m.group(2).strip().strip('"').strip("'") if m.group(2) else None
        if location:
            location = _file_location_shortcuts.get(location.lower(), os.path.expanduser(location))
            full_path = os.path.join(location, name)
        else:
            full_path = name
        return create_file(full_path)

    # ── LIST FOLDER ──
    m = re.match(r"(?:zendaya,?\s*)?(?:list|show|what'?s?\s+in)\s+(?:the\s+)?(?:folder\s+)?['\"]?(.+?)['\"]?\s*(?:folder|directory)?$", lt)
    if m and any(w in lt for w in ["list", "show", "what's in", "whats in"]):
        return list_folder(m.group(1).strip())

    # ── OPEN FOLDER ──
    m = re.match(r"(?:zendaya,?\s*)?open\s+(?:the\s+)?(?:folder\s+)?['\"]?(.+?)['\"]?\s+(?:folder|in\s+explorer|in\s+file\s+manager)$", lt)
    if m:
        return open_folder_in_explorer(m.group(1).strip())

    # ── RENAME ──
    m = re.match(r"(?:zendaya,?\s*)?rename\s+['\"]?(.+?)['\"]?\s+to\s+['\"]?(.+?)['\"]?$", lt)
    if m:
        return rename_item(m.group(1).strip(), m.group(2).strip())

    # ── SEND EMAIL ──
    m = re.match(
        r"(?:zendaya,?\s*)?send\s+(?:an?\s+)?email\s+to\s+([^\s,]+(?:@[^\s,]+)?)"
        r"(?:\s+(?:saying|with\s+subject|subject)\s+['\"]?(.+?)['\"]?)?"
        r"(?:\s+(?:saying|message|body)\s+['\"]?(.+?)['\"]?)?$",
        lt
    )
    if m:
        to_addr = m.group(1).strip()
        subject = m.group(2).strip() if m.group(2) else "Message from Zendaya"
        body    = m.group(3).strip() if m.group(3) else "(No message body provided)"
        return send_email(to_addr, subject, body)

    # ── VOLUME ──
    # Exact: "volume 50", "set volume to 80%"
    m = re.match(r"(?:zendaya,?\s*)?(?:set\s+)?volume\s+(?:to\s+)?(\d+)%?", lt)
    if m:
        return set_volume(int(m.group(1)))

    # Natural: "reduce volume", "lower the volume", "turn down the volume", "decrease volume"
    if re.search(r"\b(reduce|lower|turn\s*down|decrease|quieter)\b", lt) and re.search(r"\b(volume|sound|audio)\b", lt):
        return adjust_volume("down", 5)

    # Natural: "increase volume", "turn up the volume", "raise the volume", "louder"
    if re.search(r"\b(increase|raise|turn\s*up|louder|higher)\b", lt) and re.search(r"\b(volume|sound|audio)\b", lt):
        return adjust_volume("up", 5)

    if re.search(r"\b(mute|silence)\b", lt) and re.search(r"\b(volume|sound|audio)\b", lt):
        return mute_volume()
    if re.search(r"\bunmute\b", lt):
        return unmute_volume()

    # ── BRIGHTNESS ──
    # Exact: "brightness 50", "set brightness to 80%"
    m = re.match(r"(?:zendaya,?\s*)?(?:set\s+)?brightness\s+(?:to\s+)?(\d+)%?", lt)
    if m:
        return set_brightness(int(m.group(1)))

    # Natural: "reduce brightness", "lower brightness", "dim the screen", "make it darker"
    if re.search(r"\b(reduce|lower|turn\s*down|decrease|dim|darker)\b", lt) and re.search(r"\b(brightness|screen|display|light)\b", lt):
        return adjust_brightness("down", 15)

    # Natural: "increase brightness", "brighter", "turn up brightness"
    if re.search(r"\b(increase|raise|turn\s*up|brighter|higher|brighten)\b", lt) and re.search(r"\b(brightness|screen|display|light)\b", lt):
        return adjust_brightness("up", 15)

    # ── WALLPAPER ──
    # Set wallpaper to a specific file
    m = re.match(r"(?:zendaya,?\s*)?(?:set|change)\s+(?:my\s+)?(?:wallpaper|desktop\s*(?:background|image)|background)\s+(?:to\s+)['\"]?(.+?)['\"]?$", lt)
    if m:
        return set_wallpaper(m.group(1).strip())

    # Open wallpaper / personalization settings
    if re.search(r"\b(change|switch|set|pick|choose|new)\b", lt) and re.search(r"\b(wallpaper|background|desktop\s*(?:image|picture)?)\b", lt):
        return open_wallpaper_settings()

    # ── SCREENSHOT ──
    if re.search(r"\b(take\s+a?\s*screenshot|capture\s+(?:the\s+)?screen|screenshot)\b", lt):
        m = re.search(r"(?:name(?:d)?|called|as)\s+['\"]?([a-zA-Z0-9_\-]+\.?(?:png|jpg)?)['\"]?", lt)
        fname = (m.group(1) if m else None)
        if fname and not fname.endswith(".png"):
            fname += ".png"
        return take_screenshot(fname)

    # ── TYPE TEXT ──
    m = re.match(r"(?:zendaya,?\s*)?type\s+['\"](.+?)['\"]", original, re.IGNORECASE)
    if m:
        return type_text(m.group(1))

    # ── PRESS KEY ──
    m = re.match(r"(?:zendaya,?\s*)?press\s+(.+)$", lt)
    if m:
        return press_key(m.group(1).strip())

    # ── WINDOW MANAGEMENT ──
    if re.search(r"\blist\s+(?:open\s+)?windows\b", lt):
        return list_open_windows()

    m = re.match(r"(?:zendaya,?\s*)?(?:focus|switch\s+to|bring\s+up)\s+(.+)$", lt)
    if m and "window" in lt or "focus" in lt or "switch to" in lt:
        return focus_window(m.group(1).replace("window", "").strip())

    m = re.match(r"(?:zendaya,?\s*)?minimize\s+(.+)$", lt)
    if m:
        return minimize_window(m.group(1).strip())

    m = re.match(r"(?:zendaya,?\s*)?maximize\s+(.+)$", lt)
    if m:
        return maximize_window(m.group(1).strip())

    # ── PROCESSES ──
    m = re.match(r"(?:zendaya,?\s*)?(?:list|show)\s+(?:running\s+)?processes?(?:\s+for\s+(.+))?$", lt)
    if m:
        return list_running_processes(m.group(1) or "")

    m = re.match(r"(?:zendaya,?\s*)?kill\s+(?:process\s+)?(?:called\s+)?['\"]?(.+?)['\"]?$", lt)
    if m:
        return kill_process_by_name(m.group(1).strip())

    # ── BATTERY ──
    if re.search(r"\b(battery|charge|power)\b", lt) and re.search(r"\b(status|level|how much|remaining|check)\b", lt):
        return get_battery_status()

    # ── NETWORK ──
    if re.search(r"\b(network|wifi|wi-fi|ip\s*address|internet|connection)\s*(?:info|status|details|address)?\b", lt):
        return get_network_info()

    # ── DISK ──
    if re.search(r"\b(disk|storage|drive|space|how much space)\b", lt):
        return get_disk_usage()

    # ── REMINDER ──
    m = re.match(
        r"(?:zendaya,?\s*)?(?:set\s+a?\s*)?remind(?:er|me)\s+"
        r"(?:me\s+)?(?:in\s+)?(\d+(?:\.\d+)?)\s*(min(?:ute)?s?|hour?s?|hr?s?)\s*"
        r"(?:to\s+|about\s+|that\s+)?['\"]?(.+?)['\"]?$",
        lt
    )
    if m:
        amount = float(m.group(1))
        unit   = m.group(2)
        msg    = m.group(3).strip()
        minutes = amount * 60 if "hour" in unit or unit.startswith("h") else amount
        return set_reminder(msg, minutes)

    # ── WEBSITE ──
    m = re.match(r"(?:zendaya,?\s*)?open\s+(?:the\s+website\s+|site\s+|webpage\s+)?['\"]?(https?://[^\s'\"]+|www\.[^\s'\"]+)['\"]?", lt)
    if m:
        return open_website(m.group(1))

    # ── CLIPBOARD ──
    if re.search(r"\b(read|get|what'?s?\s+on)\s+(?:my\s+)?clipboard\b", lt):
        return get_clipboard()

    m = re.match(r"(?:zendaya,?\s*)?(?:copy|put)\s+['\"](.+?)['\"]['\"]?\s+(?:to|on|in(?:to)?)\s+(?:my\s+)?clipboard", original, re.IGNORECASE)
    if m:
        return set_clipboard(m.group(1))

    # No match — return None to fall through to Gemini
    return None
