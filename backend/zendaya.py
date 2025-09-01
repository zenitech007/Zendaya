"""
voice output is handled by ElevenLabs TTS through the speak_async function, which sends text plus the current voice_id to ElevenLabs, retrieves MP3 audio, and plays it asynchronously so text streaming isn’t blocked. User responses are taken from typed console input (input()), and while no speech recognition is included, the script routes typed commands through parsers that detect mode switches, voice switches, system commands, searches, or normal chat. Switching voices happens when a user types something like “Zendaya, switch to narrator voice,” which the script catches with parse_voice_switch, resolves the requested preset or name with find_voice_by_free_text, updates MEM["current_voice_id"], and applies it to all future TTS. Switching modes between voice, text, or both is handled by parse_mode_switch and set_mode, which update memory and change whether replies are printed (stream_print), spoken (speak_async), or both. Finally, memory persistence via zendaya_memory.json stores the current mode, active voice, conversation history, and pending actions so the assistant remembers user preferences and context across sessions.
"""
import os
import re
import json
import time
import shutil
import random
import difflib # Added for fuzzy matching
import platform
import subprocess
import webbrowser
import threading # Added for async audio playback
from typing import Optional, Dict, Any, List
from collections import Counter
from datetime import datetime, timezone

# --- Google API & Auth Imports ---
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Tier 1 Library Imports ---
import psutil
import pyperclip
import pyttsx3
import pygetwindow as gw
if platform.system() == "Windows":
    try:
        from win10toast import ToastNotifier
    except ImportError:
        print("Warning: win10toast not installed. Run 'pip install win10toast' for notification features.")

# --- Python Library Imports ---
import requests
from dotenv import load_dotenv
import google.generativeai as genai
try:
    from playsound import playsound
except ImportError:
    print("Warning: playsound not installed. Run 'pip install playsound' for audio features.")


# For Windows specific window handling
if platform.system() == "Windows":
    try:
        import win32api, win32con, win32gui, win32process
    except ImportError:
        print("Warning: pywin32 not installed. Some advanced Windows window controls may not work.")

# -----------------------
# Load keys & config
# -----------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        _GEMINI_READY = True
    except Exception as e:
        print(f"Gemini API configuration failed: {e}")
        _GEMINI_READY = False
else:
    _GEMINI_READY = False
    print("Warning: GEMINI_API_KEY is not set. Conversational features will be limited.")

_ELEVENLABS_READY = bool(ELEVENLABS_API_KEY)
if not _ELEVENLABS_READY:
    print("Warning: ELEVENLABS_API_KEY is not set. Voice features will fall back to system TTS.")

# -----------------------
# Files, Constants & Scopes
# -----------------------
MEMORY_FILE = "zendaya_memory.json"
DEFAULT_MODE = "both"
PERSONA_NAME = "Zendaya"
ASSISTANT_NAME = "Zendaya"
ELEVENLABS_DEFAULT_VOICE_ID = "mxTlDrtKZzOqgjtBw4hM"

# --- Other Constants ---
AUTO_SEARCH_KEYWORDS = [
    "latest", "today", "breaking", "news", "trending", "score",
    "price", "weather", "exchange rate", "update", "who won", "market", "live",
    "forecast", "definition", "meaning", "how to", "what is"
]

# Force ElevenLabs voice ID - override memory settings
FORCE_ELEVENLABS_VOICE_ID = "mxTlDrtKZzOqgjtBw4hM"

# Google API Scopes
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# --------------------------------------------------------
# 🔹 ElevenLabs TTS & System Fallback
# --------------------------------------------------------
_TTS_ENGINE = None

def _play_audio_async(file_path):
    """Helper to play audio in a separate thread."""
    def target():
        try:
            if 'playsound' in globals():
                playsound(file_path)
            os.remove(file_path) # Clean up the temp file
        except Exception as e:
            print(f"(Audio playback error: {e})")
    
    threading.Thread(target=target).start()

def speak_async(text: str, voice_id: str):
    """Sends text to ElevenLabs and plays the audio asynchronously."""
    # Force use of specific ElevenLabs voice ID
    voice_id = FORCE_ELEVENLABS_VOICE_ID
    
    if not _ELEVENLABS_READY or 'playsound' not in globals():
        speak_system_fallback(text)
        return

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": { "stability": 0.5, "similarity_boost": 0.75 }
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=20)
        if response.status_code == 200:
            temp_file = "temp_audio.mp3"
            with open(temp_file, "wb") as f:
                f.write(response.content)
            _play_audio_async(temp_file)
        else:
            print(f"(ElevenLabs API Error: {response.status_code} - {response.text})")
            speak_system_fallback(text) # Fallback on API error
    except Exception as e:
        print(f"(ElevenLabs request failed: {e})")
        speak_system_fallback(text) # Fallback on request error

def initialize_system_tts():
    """Initializes the pyttsx3 engine as a fallback."""
    global _TTS_ENGINE
    if _TTS_ENGINE: return True
    try:
        print("🔄 Initializing system Text-to-Speech engine as fallback...")
        _TTS_ENGINE = pyttsx3.init()
        voices = _TTS_ENGINE.getProperty('voices')
        female_voice = next((voice for voice in voices if voice.gender == 'female'), None)
        if female_voice:
            _TTS_ENGINE.setProperty('voice', female_voice.id)
        print("✅ System TTS engine loaded.")
        return True
    except Exception as e:
        print(f"❌ CRITICAL: Failed to initialize system TTS engine. Voice output will be disabled.")
        print(f"   Error details: {e}")
        return False

def speak_system_fallback(text: str):
    """Speak text using the system's TTS engine if ElevenLabs fails."""
    # In voice mode, we don't need to print the name again
    if MEM["mode"] not in ("voice"):
        print(f"🗣️ [{ASSISTANT_NAME}] {text}")

    if not initialize_system_tts():
        print("⚠️ TTS engine not ready.")
        return
    try:
        _TTS_ENGINE.say(text)
        _TTS_ENGINE.runAndWait()
    except Exception as e:
        print(f"Error during system TTS playback: {e}")


# -----------------------
# Memory persistence
# -----------------------
def load_memory() -> Dict[str, Any]:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return {
        "mode": DEFAULT_MODE, "convo": [],
        "inside_jokes": [], "pending_confirm": None, "user_name": None,
        "command_history": [], "routines": {}, "summaries": [],
        "professional_mode": False,
        "current_voice_id": ELEVENLABS_DEFAULT_VOICE_ID
    }

def save_memory(mem: Dict[str, Any]) -> None:
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"(Memory save error: {e})")

MEM = load_memory()

# -----------------------
# Core Assistant Functions
# -----------------------
def stream_print(text: str, delay: float = 0.01):
    print(f"{ASSISTANT_NAME}: ", end="")
    for ch in text:
        print(ch, end="", flush=True)
        time.sleep(delay)
    print()

def send_response(text: str):
    if MEM["mode"] in ("both", "text"):
        stream_print(text)
    if MEM["mode"] in ("both", "voice"):
        speak_async(text, FORCE_ELEVENLABS_VOICE_ID)

# -------------------------------------------------
# TIER 1 FEATURE: GOOGLE API SECURE AUTHENTICATION
# -------------------------------------------------
def get_google_service(api_name: str, api_version: str, scopes: List[str]):
    """Handles the OAuth2 flow and returns an authenticated service object."""
    creds = None
    token_file = f'token_{api_name}.json'
    
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Could not refresh token for {api_name}: {e}")
                creds = None
        
        if not creds:
            if not os.path.exists('credentials.json'):
                print("ERROR: `credentials.json` not found. Please follow setup instructions.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', scopes)
            creds = flow.run_local_server(port=0)
        
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
            
    try:
        service = build(api_name, api_version, credentials=creds)
        return service
    except HttpError as error:
        print(f'An error occurred building the service: {error}')
        return None

# -------------------------------------------------
# TIER 1 FEATURE: EMAIL & CALENDAR (Functional)
# -------------------------------------------------
def check_email(max_results: int = 3) -> str:
    service = get_google_service('gmail', 'v1', GMAIL_SCOPES)
    if not service:
        return "I couldn't connect to your Gmail account."
    try:
        results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD'], maxResults=max_results).execute()
        messages = results.get('messages', [])
        if not messages:
            return "Your inbox is clear. No unread emails."
        email_summaries = []
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = msg['payload']['headers']
            subject = next(h['value'] for h in headers if h['name'] == 'Subject')
            sender = next(h['value'] for h in headers if h['name'] == 'From')
            email_summaries.append(f"From {sender.split('<')[0].strip()}, subject: {subject}")
        return f"You have {len(messages)} unread emails. Here are the latest:\n" + "\n".join(email_summaries)
    except HttpError as error:
        return f"An error occurred checking email: {error}"

def check_calendar(max_results: int = 5) -> str:
    service = get_google_service('calendar', 'v3', CALENDAR_SCOPES)
    if not service:
        return "I couldn't connect to your Google Calendar."
    try:
        now = datetime.now(timezone.utc).isoformat()
        events_result = service.events().list(
            calendarId='primary', timeMin=now,
            maxResults=max_results, singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        if not events:
            return "You have no upcoming events."
        event_summaries = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            start_dt = datetime.fromisoformat(start)
            formatted_time = start_dt.strftime('%A at %I:%M %p')
            event_summaries.append(f"- {event['summary']} on {formatted_time}")
        return f"Here are your next {len(events)} events:\n" + "\n".join(event_summaries)
    except HttpError as error:
        return f"An error occurred checking the calendar: {error}"

# -------------------------------------------------
# TIER 1 FEATURE: SYSTEM MONITORING, CLIPBOARD, FILES
# -------------------------------------------------
def get_system_performance() -> str:
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return f"System status: CPU at {cpu}%. Memory at {mem.percent}%. Disk at {disk.percent}%."

def read_clipboard() -> str:
    try:
        content = pyperclip.paste()
        return f"Clipboard contains: {content}" if content else "The clipboard is empty."
    except Exception:
        return "Sorry, I couldn't read the clipboard."

def write_to_clipboard(text: str) -> str:
    try:
        pyperclip.copy(text)
        return "Copied to clipboard."
    except Exception:
        return "I couldn't write to the clipboard."

def find_file(filename: str, search_path: str = None) -> str:
    path = search_path or os.path.expanduser("~")
    send_response(f"Searching for '{filename}'...")
    for root, _, files in os.walk(path):
        if filename in files:
            found = os.path.join(root, filename)
            return f"File found at: {found}"
    return f"Couldn't find '{filename}'."

def read_file_content(filepath: str) -> str:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if len(content) > 2000:
            send_response("File is large, summarizing...")
            model = genai.GenerativeModel("gemini-1.5-flash")
            resp = model.generate_content(f"Summarize this:\n\n{content[:2000]}")
            return f"Summary:\n{resp.text.strip()}"
        return f"Content:\n{content}"
    except Exception as e:
        return f"Error reading file: {e}"

def manage_file(action: str, source: str, destination: str = None) -> str:
    if not os.path.exists(source): return f"Source '{source}' does not exist."
    try:
        if action == "copy":
            if not destination: return "I need a destination."
            shutil.copy(source, destination)
            return f"Copied '{os.path.basename(source)}'."
        elif action == "move":
            if not destination: return "I need a destination."
            shutil.move(source, destination)
            return f"Moved '{os.path.basename(source)}'."
        elif action == "delete":
            MEM["pending_confirm"] = {"action": "delete_file", "path": source}
            save_memory(MEM)
            return f"Please confirm deletion of '{os.path.basename(source)}'."
    except Exception as e:
        return f"Error: {e}"

def show_notification(title: str, message: str) -> str:
    if platform.system() == "Windows" and 'ToastNotifier' in globals():
        ToastNotifier().show_toast(title, message, duration=10, threaded=True)
        return "Notification sent."
    return "Notifications only supported on Windows with win10toast installed."

# -----------------------
# Tavily search
# -----------------------
def tavily_search(query: str) -> str:
    if not TAVILY_API_KEY:
        return "(Search unavailable — missing TAVILY_API_KEY)"
    try:
        r = requests.post("https://api.tavily.com/search",
                          json={"api_key": TAVILY_API_KEY, "query": query, "search_depth": "basic", "max_results": 5},
                          timeout=25)
        data = r.json()
        items = data.get("results", [])
        if not items:
            return "No search results found."
        lines = []
        for it in items:
            title = it.get("title", "untitled")
            snippet = (it.get("content") or "")[:220].replace("\n", " ")
            lines.append(f"- {title}: {snippet} (source)")
        return "\n".join(lines)
    except Exception as e:
        return f"(Search error: {e})"

def should_auto_search(txt: str) -> bool:
    l = txt.lower()
    return any(k in l for k in AUTO_SEARCH_KEYWORDS)

# -----------------------
# Gemini reply composition
# -----------------------
SYSTEM_PROMPT = (
    "You are Zendaya, a brilliant, witty, confident, and slightly teasing AI assistant, inspired by characters like Shuri from Black Panther. "
    "Speak like a friendly genius, keeping answers concise (<6 sentences) when possible. "
    "Use provided search snippets to directly answer questions and provide up-to-date information. "
    "Do not hallucinate or make up facts. Add occasional playful quips. "
    "When a user asks you to perform a task like opening an app, respond with a short confirmation message, not a long conversational response. "
    "If 'professional_mode' is active, your tone must be strictly formal, direct, and professional. Omit all quips, teasing, and persona-driven language."
)

def gemini_reply(user_text: str, search_context: Optional[str]) -> str:
    if not _GEMINI_READY:
        return "My online brain is offline — add GEMINI_API_KEY to .env."
    model = genai.GenerativeModel("gemini-1.5-flash")
    memory_bits = []
    
    if MEM.get("professional_mode", False):
        memory_bits.append("IMPORTANT: Professional mode is active. Your response must be formal.")

    if MEM.get("user_name"):
        memory_bits.append(f"The user's name is {MEM['user_name']}.")

    if MEM.get("inside_jokes"):
        memory_bits.append("Inside jokes: " + ", ".join(MEM["inside_jokes"][-3:]))
    if MEM.get("convo"):
        tail = [f"{x['role']}: {x['text']}" for x in MEM["convo"][-6:]]
        memory_bits.append("Recent context:\n" + "\n".join(tail))
    if MEM.get("summaries"):
        memory_bits.append("Summarized context:\n" + "\n".join(MEM["summaries"][-3:]))

    parts = [SYSTEM_PROMPT]
    if memory_bits:
        parts.append("\n".join(memory_bits))

    if search_context:
        parts.append(f"Search snippets:\n{search_context}\n")

    parts.append(f"User: {user_text}\n{PERSONA_NAME}:")

    try:
        resp = model.generate_content(parts)
        return resp.text.strip()
    except Exception as e:
        return f"(AI error: {e})"

# -----------------------
# Command Parsers
# -----------------------
def parse_name_introduction(user_text: str) -> Optional[str]:
    """Parses text to see if the user is introducing themselves."""
    # Regex to find patterns like "my name is Larry", "call me Larry", "I'm Larry"
    match = re.search(r"\b(?:my\s+name\s+is|call\s+me|i'm|i\s+am)\s+([a-zA-Z]+)\b", user_text, re.IGNORECASE)
    if match:
        return match.group(1).capitalize()
    return None

def parse_tier1_commands(user_text: str) -> Optional[Dict[str, Any]]:
    lt = user_text.lower().strip()
    if re.search(r"\b(system status|pc performance)\b", lt): return {"type": "system_status"}
    if re.search(r"\b(read|what's on)\s+my\s+clipboard\b", lt): return {"type": "read_clipboard"}
    m_copy = re.match(r"copy\s+(?:this|that)\s+to\s+clipboard", lt)
    if m_copy:
        last_response = MEM.get("convo", [])[-1].get("text")
        return {"type": "write_clipboard", "content": last_response} if last_response else {"type": "error", "message": "No response to copy."}
    m_find = re.match(r"find\s+file\s+(.+)", lt)
    if m_find: return {"type": "find_file", "filename": m_find.group(1)}
    m_read = re.match(r"read\s+file\s+(.+)", lt)
    if m_read: return {"type": "read_file", "filepath": m_read.group(1)}
    m_manage = re.match(r"(copy|move|delete)\s+(.+?)(?:\s+to\s+(.+))?$", lt)
    if m_manage:
        return {"type": "manage_file", "action": m_manage.group(1), "source": m_manage.group(2).strip(), "destination": m_manage.group(3).strip() if m_manage.group(3) else None}
    if re.search(r"\b(check my email)\b", lt): return {"type": "check_email"}
    if re.search(r"\b(check my calendar)\b", lt): return {"type": "check_calendar"}
    return None

def parse_manual_search(user_text: str) -> Optional[str]:
    m = re.match(r"^(?:zendaya,\s*)?(?:search|look up|find|what is|tell me about|how to)\s+(.+)$", user_text.strip(), re.IGNORECASE)
    if not m:
        return None
    return m.group(1).strip()

def parse_mode_switch(user_text: str) -> Optional[str]:
    lt = user_text.lower().strip()
    if re.match(r"^(?:zendaya,\s*)?(?:voice only|speak only)$", lt):
        return "voice"
    if re.match(r"^(?:zendaya,\s*)?text only$", lt):
        return "text"
    if re.match(r"^(?:zendaya,\s*)?(?:type and speak|text and voice|both)$", lt):
        return "both"
    return None

def handle_mode_switch(user_text: str) -> Optional[str]:
    mode = parse_mode_switch(user_text)
    if mode:
        MEM["mode"] = mode
        save_memory(MEM)
        return f"Mode set to: {mode}"
    return None

def parse_professional_mode_toggle(user_text: str) -> Optional[bool]:
    """Checks for commands to toggle professional mode. Returns True for on, False for off."""
    lt = user_text.lower().strip()
    if re.search(r"\b(enter|start|enable|activate)\s+professional\s+mode\b", lt):
        return True
    if re.search(r"\b(exit|stop|disable|deactivate)\s+professional\s+mode\b", lt):
        return False
    return None

def parse_routine_command(user_text: str) -> Optional[str]:
    m = re.match(r"^(?:zendaya,\s*)?(?:run|start)\s+(?:my\s+)?(.+?)\s+routine\s*$", user_text.strip(), re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None

def parse_system_control(user_text) -> Optional[Dict[str, str]]:
    lt = user_text.lower().strip()

    m_open = re.match(r"^(?:zendaya,\s*)?(?:open|launch|start)\s+(.+)$", lt)
    if m_open:
        return {"type": "open", "target": m_open.group(1).strip()}

    m_close = re.match(r"^(?:zendaya,\s*)?(?:close|quit|kill|exit)\s+(.+)$", lt)
    if m_close:
        return {"type": "close", "target": m_close.group(1).strip()}

    for action in ("shutdown", "restart", "sleep", "lock"):
        if re.search(r"^(?:zendaya,\s*)?" + re.escape(action) + r"(?:\s+pc|\s+computer)?$", lt):
            return {"type": "system", "target": action}

    return None

def handle_self_inquiry(is_professional: bool) -> str:
    """Generates a dynamic response about Zendaya's identity."""
    base_intro = "I'm Zendaya, your technical genius and personal AI assistant."
    acronym_def = "My name is an acronym, Z.E.N.D.A.Y.A. – which stands for Zettascale Engine for Neural Decision-making and Autonomous Yield Augmentation."
    purpose_stmt = "Basically, I'm built to automate your habits, learn your routines, and handle mundane tasks so you don't have to."
    goal_stmt = "My goal is to make your life more efficient and a whole lot cooler."
    closing = "My tech is always at your service."

    if is_professional:
        return f"{base_intro} {acronym_def} {purpose_stmt} My goal is to enhance your efficiency."

    # For normal mode, make it more lively and varied
    openers = ["You want to know about little ol' me? Alright, here's the deal.", "So, you're curious? I like that. Let's see...", "About me? Oh, where to begin!"]
    
    return f"{random.choice(openers)}\n{base_intro} {acronym_def}\n{purpose_stmt} {goal_stmt} {closing}"

def find_app_path(app_name: str) -> Optional[str]:
    """Finds an application's executable path, with typo correction."""
    system = platform.system().lower()
    os_key = {"windows": "win", "darwin": "mac", "linux": "linux"}.get(system, "linux")
    
    app_map = {
        "chrome": {"win": "chrome.exe", "mac": "Google Chrome.app", "linux": "google-chrome"},
        "firefox": {"win": "firefox.exe", "mac": "Firefox.app", "linux": "firefox"},
        "vscode": {"win": "Code.exe", "mac": "Visual Studio Code.app", "linux": "code"},
        "notepad": {"win": "notepad.exe", "mac": None, "linux": "gedit"},
        "notepad++": {"win": "notepad++.exe", "mac": None, "linux": "notepadqq"},
        "calculator": {"win": "calc.exe", "mac": "Calculator.app", "linux": "gnome-calculator"},
        "spotify": {"win": "Spotify.exe", "mac": "Spotify.app", "linux": "spotify"},
        "brave": {"win": "brave.exe", "mac": "Brave Browser.app", "linux": "brave-browser"},
        "edge": {"win": "msedge.exe", "mac": "Microsoft Edge.app", "linux": "microsoft-edge-stable"},
        "paint": {"win": "mspaint.exe", "mac": None, "linux": "kolourpaint"},
        "file explorer": {"win": "explorer.exe", "mac": None, "linux": "nautilus"}
    }
    
    app_name_lower = app_name.lower().strip()
    
    # --- Fuzzy Matching Logic ---
    if app_name_lower not in app_map:
        matches = difflib.get_close_matches(app_name_lower, app_map.keys(), n=1, cutoff=0.7)
        if matches:
            corrected_name = matches[0]
            send_response(f"Did you mean '{corrected_name.capitalize()}'? I'll open that.")
            app_name_lower = corrected_name
        else:
            return None # No close match found
    
    exec_name = app_map.get(app_name_lower, {}).get(os_key)
    
    if exec_name:
        try:
            cmd = ["where", exec_name] if system == "windows" else ["which", exec_name]
            creationflags = subprocess.CREATE_NO_WINDOW if system == "windows" else 0
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=creationflags)
            return result.stdout.splitlines()[0].strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
             # Fallback for Windows if 'where' fails
            if system == "windows":
                app_dir_name = app_name_lower.split(' ')[0] # e.g., 'visual studio code' -> 'visual studio code'
                common_paths = [os.path.join(os.environ.get("ProgramFiles", ""), app_dir_name, exec_name),
                                os.path.join(os.environ.get("ProgramFiles(x86)", ""), app_dir_name, exec_name),
                                os.path.join(os.environ.get("LocalAppData", ""), "Programs", app_dir_name, exec_name)]
                for path in common_paths:
                    if os.path.exists(path):
                        return path
    
    return None # If all methods fail

def open_target(target: str) -> str:
    t = target.lower().strip()
    shortcuts = {"youtube": "https://www.youtube.com", "google": "https://www.google.com", "gmail": "https://mail.google.com", "mails": "https://mail.google.com"}
    if t in shortcuts:
        webbrowser.open(shortcuts[t])
        return f"Opening {t}."

    app_path = find_app_path(t)
    if app_path:
        try:
            if platform.system() == "Windows":
                os.startfile(app_path)
            elif platform.system() == "Darwin": # macOS
                subprocess.Popen(["open", "-a", app_path])
            else: # Linux
                subprocess.Popen([app_path], start_new_session=True)
            return f"Launching {os.path.basename(app_path)}."
        except Exception as e:
            return f"I tried to launch {t} but encountered an error: {e}"

    if t.startswith("http://") or t.startswith("https://"):
        webbrowser.open(t)
        return "Opening the URL."

    return f"I couldn't find or open '{target}'. Is it installed?"


def close_target(target: str) -> str:
    t = target.lower().strip()
    proc_map = {
        "chrome": "chrome.exe", "edge": "msedge.exe", "notepad": "notepad.exe",
        "notepad++": "notepad++.exe",
        "vscode": "Code.exe", "spotify": "Spotify.exe", "firefox": "firefox.exe",
        "brave": "brave.exe", "calculator": "calc.exe", "paint": "mspaint.exe"
    }

    if platform.system() == "Windows":
        proc_name = proc_map.get(t)
        if not proc_name:
            windows = gw.getWindowsWithTitle(target)
            if windows and "win32process" in globals():
                try:
                    pid = win32process.GetWindowThreadProcessId(windows[0]._hWnd)[1]
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, check=True)
                    return f"Closed {target}."
                except Exception as e:
                    return f"Could not close {target} by PID: {e}"
            return f"I don't have a defined process name for '{target}' and couldn't find its window."
        try:
            subprocess.run(["taskkill", "/IM", proc_name, "/F"], capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return f"Closed {target}."
        except Exception:
            return f"Could not close {target}. Is it running?"
    else: # macOS and Linux
        try:
            # Use pkill which is common on both
            subprocess.run(["pkill", "-f", "-i", t], check=True) # -i for case-insensitive
            return f"Attempted to close {target}."
        except Exception as e:
            return f"Could not close {target}: {e}"


def queue_dangerous(action: str) -> str:
    MEM["pending_confirm"] = action
    save_memory(MEM)
    return f"{action.capitalize()} queued. Say: '{ASSISTANT_NAME}, confirm {action}' to proceed."

def confirm_dangerous(user_text: str) -> Optional[str]:
    lt = user_text.lower().strip()
    pending_action = MEM.get("pending_confirm")

    if not pending_action or "confirm" not in lt:
        return None

    confirmed = False
    action_type = ""
    
    # Handle string-based actions (shutdown, restart, etc.)
    if isinstance(pending_action, str):
        if f"confirm {pending_action}" in lt:
            action_type = pending_action
            confirmed = True

    # Handle dict-based actions (file deletion)
    elif isinstance(pending_action, dict) and pending_action.get("action") == "delete_file":
        # A simple "confirm deletion" or "confirm" should be enough here
        if "delete" in lt or "yes" in lt or "confirm" in lt:
            action_type = "delete_file"
            confirmed = True

    if not confirmed:
        return None

    # --- Execute Confirmed Action ---
    MEM["pending_confirm"] = None
    save_memory(MEM)

    try:
        if action_type == "shutdown":
            cmd = ["shutdown", "/s", "/t", "1"] if platform.system() == "Windows" else ["shutdown", "-h", "now"]
            subprocess.Popen(cmd)
            return "Shutting down now. Goodbye."
        if action_type == "restart":
            cmd = ["shutdown", "/r", "/t", "1"] if platform.system() == "Windows" else ["shutdown", "-r", "now"]
            subprocess.Popen(cmd)
            return "Restarting now."
        if action_type == "sleep":
            cmd = ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"] if platform.system() == "Windows" else ["pm-suspend"]
            subprocess.Popen(cmd)
            return "Going to sleep."
        if action_type == "lock":
            if platform.system() == "Windows":
                 subprocess.Popen(["Rundll32.exe", "user32.dll,LockWorkStation"])
            else:
                lock_cmds = ["gnome-screensaver-command -l", "dm-tool lock", "xscreensaver-command -lock"]
                for cmd_str in lock_cmds:
                    try:
                        subprocess.Popen(cmd_str.split())
                        break
                    except FileNotFoundError:
                        continue
            return "Locked."
        if action_type == "delete_file":
            filepath = pending_action.get("path")
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                return f"File '{os.path.basename(filepath)}' has been deleted."
            return "Could not delete the file. It might have been moved or already deleted."
            
    except Exception as e:
        return f"I tried but the system returned an error: {e}"
        
    return "Action confirmed, but I don't know how to perform it."

# -----------------------
# Memory helpers
# -----------------------
def add_to_memory(role: str, text: str):
    MEM.setdefault("convo", []).append({"role": role, "text": text, "ts": datetime.now().isoformat()})
    if len(MEM["convo"]) > 30:
        MEM["convo"] = MEM["convo"][-30:]
    save_memory(MEM)

def summarize_memory():
    history = MEM.get("convo", [])
    if len(history) < 20: return

    to_summarize = history[:10]
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = "Summarize this conversation in short bullets, keeping key preferences and context. Omit small talk."
        convo_text = "\n".join([f"{m['role']}: {m['text']}" for m in to_summarize])
        resp = model.generate_content([prompt, convo_text])
        summary = resp.text.strip()
        MEM.setdefault("summaries", []).append(summary)
        MEM["convo"] = history[10:]
        save_memory(MEM)
        print("(Memory summarized)")
    except Exception as e:
        print(f"(Memory summarization error: {e})")

# -----------------------
# Routine execution
# -----------------------
def run_routine(routine_name: str):
    routine_commands = MEM["routines"].get(routine_name.lower())
    if not routine_commands:
        reply = f"I couldn't find a routine named '{routine_name}'. Did you create it yet?"
        send_response(reply)
        return

    reply = f"Starting the '{routine_name}' routine. Let's get this done."
    send_response(reply)

    for command in routine_commands:
        time.sleep(1)
        send_response(f"-> Executing: '{command}'")

        sysc = parse_system_control(command)
        if sysc:
            if sysc["type"] == "open":
                open_target(sysc["target"])
            elif sysc["type"] == "close":
                close_target(sysc["target"])
            elif sysc["type"] == "system":
                send_response(f"Routine command '{command}' involves a system action that requires manual confirmation.")
        else:
            send_response(f"Could not execute routine step: '{command}'")

    final_reply = "Routine complete. My work here is done."
    send_response(final_reply)

# ----------------------------------------------------
# 🔹 Main Command Handler (Refactored)
# ----------------------------------------------------
def handle_user_command(user_text: str):
    """
    Processes the user's text, executes commands, and generates an AI response.
    """
    add_to_memory("user", user_text)

    # --- Handle high-priority commands and direct interactions first ---
    conf = confirm_dangerous(user_text)
    if conf:
        send_response(conf)
        return

    mode_switch_msg = handle_mode_switch(user_text)
    if mode_switch_msg:
        send_response(mode_switch_msg)
        return
        
    prof_mode_toggle = parse_professional_mode_toggle(user_text)
    if prof_mode_toggle is not None:
        MEM["professional_mode"] = prof_mode_toggle
        save_memory(MEM)
        if prof_mode_toggle:
            send_response("Professional mode activated. I will now maintain a formal tone.")
        else:
            send_response("Professional mode deactivated. Back to our regularly scheduled genius.")
        return

    # --- Check for self-introduction ---
    user_name = parse_name_introduction(user_text)
    if user_name:
        MEM["user_name"] = user_name
        save_memory(MEM)
        send_response(f"Nice to meet you, {user_name}! I'll remember that.")
        return

    # --- Check for self-inquiry (what are you, etc.) ---
    self_inquiry_pattern = r"\b(what are you|who are you|tell me about yourself|what is zendaya|meaning of zendaya|know you|why do they call you)\b"
    if re.search(self_inquiry_pattern, user_text.lower()):
        response = handle_self_inquiry(MEM.get("professional_mode", False))
        send_response(response)
        add_to_memory(PERSONA_NAME, response)
        return

    # --- Functional Commands (Tier 1 & System) ---
    tier1_cmd = parse_tier1_commands(user_text)
    if tier1_cmd:
        cmd_type = tier1_cmd.get("type")
        response = "Sorry, I had an issue with that command."
        if cmd_type == "system_status": response = get_system_performance()
        elif cmd_type == "read_clipboard": response = read_clipboard()
        elif cmd_type == "write_clipboard": response = write_to_clipboard(tier1_cmd["content"])
        elif cmd_type == "find_file": response = find_file(tier1_cmd["filename"])
        elif cmd_type == "read_file": response = read_file_content(tier1_cmd["filepath"])
        elif cmd_type == "manage_file": response = manage_file(tier1_cmd["action"], tier1_cmd["source"], tier1_cmd.get("destination"))
        elif cmd_type == "check_email": response = check_email()
        elif cmd_type == "check_calendar": response = check_calendar()
        elif cmd_type == "error": response = tier1_cmd["message"]
        send_response(response)
        return

    sysc = parse_system_control(user_text)
    if sysc:
        if sysc["type"] == "open": msg = open_target(sysc["target"])
        elif sysc["type"] == "close": msg = close_target(sysc["target"])
        else: msg = queue_dangerous(sysc["target"])
        send_response(msg)
        return
    
    # --- If no command, handle as conversational query ---
    search_context = None
    if should_auto_search(user_text):
        send_response("Searching the network for you...")
        search_context = tavily_search(user_text)

    ai_text = gemini_reply(user_text, search_context)
    
    add_to_memory(PERSONA_NAME, ai_text)
    send_response(ai_text)
    summarize_memory()

# -----------------------
# Main loop
# -----------------------
def main():
    user_name = MEM.get("user_name")
    welcome_message = f"Welcome back, {user_name}." if user_name else "Welcome back."
    
    if _ELEVENLABS_READY:
        send_response(f"{welcome_message} My systems are online and ready.")
    else:
        print(f"{welcome_message} My systems are online. (ElevenLabs key missing, using system TTS)")
        # Attempt to use system TTS for the welcome message
        if MEM["mode"] in ("both", "voice"):
             speak_system_fallback(f"{welcome_message} My systems are online and ready.")

    EXIT_COMMANDS = ["exit", "quit", "bye", "goodbye", "farewell"]

    try:
        while True:
            user_text = input("\nYou: ").strip()

            if not user_text:
                continue

            # Fuzzy matching for exit commands
            close_matches = difflib.get_close_matches(user_text.lower(), EXIT_COMMANDS, n=1, cutoff=0.7)
            if close_matches:
                bye = "Farewell. Don’t cause trouble without me."
                send_response(bye)
                break

            handle_user_command(user_text)

    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
        bye = "Deactivating. Talk to you later."
        send_response(bye)
        time.sleep(2)
    finally:
        print("System shutdown complete.")

if __name__ == "__main__":
    main()



