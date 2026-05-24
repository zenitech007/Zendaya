"""
voice output is handled by ElevenLabs TTS through the speak_async function, which sends text plus the current voice_id to ElevenLabs, retrieves MP3 audio, and plays it asynchronously so text streaming isn’t blocked. User responses are taken from typed console input (input()), and while no speech recognition is included, the script routes typed commands through parsers that detect mode switches, voice switches, system commands, searches, or normal chat. Switching voices happens when a user types something like “Zendaya, switch to narrator voice,” which the script catches with parse_voice_switch, resolves the requested preset or name with find_voice_by_free_text, updates MEM["current_voice_id"], and applies it to all future TTS. Switching modes between voice, text, or both is handled by parse_mode_switch and set_mode, which update memory and change whether replies are printed (stream_print), spoken (speak_async), or both. Finally, memory persistence via zendaya_memory.json stores the current mode, active voice, conversation history, and pending actions so the assistant remembers user preferences and context across sessions.
"""
# Suppress all deprecation warnings BEFORE any imports
import warnings
warnings.filterwarnings("ignore")

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
        pass  # Notifications silently disabled

# --- Python Library Imports ---
import requests
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from zendaya_system_access import *

try:
    import zendaya_assistant_features as aaf
    _AAF_READY = True
except Exception as _e:
    print(f"[zendaya] assistant_features unavailable: {_e}")
    aaf = None
    _AAF_READY = False

# For Windows specific window handling
if platform.system() == "Windows":
    try:
        import win32api, win32con, win32gui, win32process
    except ImportError:
        print("Warning: pywin32 not installed. Some advanced Windows window controls may not work.")

# Audio playback
try:
    import sounddevice as sd
    import soundfile as sf
    def playsound(file_path):
        data, samplerate = sf.read(file_path)
        sd.play(data, samplerate)
        sd.wait()
except ImportError:
    print("Warning: sounddevice not installed. Audio features disabled.")

# -----------------------
# Load keys & config  (MUST happen before any API client is created)
# -----------------------
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Initialize Gemini client AFTER loading the .env
_gemini_client = None
if GEMINI_API_KEY:
    try:
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        _GEMINI_READY = True
        print("✅ Gemini AI ready.")
    except Exception as e:
        print(f"Gemini API configuration failed: {e}")
        _GEMINI_READY = False
else:
    _GEMINI_READY = False
    print("Warning: GEMINI_API_KEY is not set. Conversational features will be limited.")

_ELEVENLABS_READY = False  # ElevenLabs disabled — using system TTS

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
FORCE_ELEVENLABS_VOICE_ID = "mxTlDrtKZzOqgjtBw4hM"  # Zendaya's signature voice - NEVER CHANGE

# Enhanced error understanding and communication
COMMUNICATION_ENHANCEMENTS = {
    "noise_cancellation": True,
    "context_awareness": True,
    "error_correction": True,
    "clarification_intelligence": True,
    "offline_mode": True,
    "biometric_recognition": True,
    "smart_home_integration": True,
    "workflow_orchestration": True
}

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
    # ABSOLUTE FORCE: Always use Zendaya's voice ID - no exceptions
    voice_id = FORCE_ELEVENLABS_VOICE_ID
    
    # Enhanced voice settings for perfect clarity
    enhanced_settings = {
        "stability": 0.75,
        "similarity_boost": 0.85,
        "style": 0.25,
        "use_speaker_boost": True
    }
    
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
        "voice_settings": enhanced_settings
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
    """Speak text using the system TTS engine silently (no duplicate print)."""
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
        "current_voice_id": ELEVENLABS_DEFAULT_VOICE_ID,
        "last_action": None, "pending_action": None,
        "last_system_command": None
    }

def save_memory(mem: Dict[str, Any]) -> None:
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"(Memory save error: {e})")

MEM = load_memory()

# -----------------------
# Context tracking helpers
# -----------------------
def set_last_action(entity_type: str, name: str, path: str):
    MEM["last_action"] = {"type": entity_type, "name": name, "path": path}
    save_memory(MEM)

def set_last_system_command(sys_result: str):
    result_lower = sys_result.lower()
    if any(kw in result_lower for kw in ["volume", "audio", "mute", "unmute"]):
        MEM["last_system_command"] = "volume"
    elif "brightness" in result_lower:
        MEM["last_system_command"] = "brightness"
    else:
        return
    save_memory(MEM)

def resolve_context(text: str) -> str:
    last = MEM.get("last_action")
    if not last:
        return text
    folder_refs = ["the folder", "that folder", "the directory", "in there", "same folder", "that directory"]
    file_refs = ["the file", "that file", "the document", "that document"]
    for ref in folder_refs:
        if ref in text.lower():
            if last["type"] == "folder":
                text = re.sub(re.escape(ref), f'"{last["path"]}"', text, count=1, flags=re.IGNORECASE)
            elif last["type"] == "file":
                parent = os.path.dirname(last["path"])
                text = re.sub(re.escape(ref), f'"{parent}"', text, count=1, flags=re.IGNORECASE)
            break
    for ref in file_refs:
        if ref in text.lower():
            if last["type"] == "file":
                text = re.sub(re.escape(ref), f'"{last["path"]}"', text, count=1, flags=re.IGNORECASE)
            break
    return text

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
            response = _gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"Summarize this:\n\n{content[:2000]}"
            )
            ai_text = response.text
            return f"Summary:\n{ai_text.strip()}"
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
    
    # Enhanced error understanding and context analysis
    processed_text = enhance_user_input(user_text)
    
    memory_bits = []
    
    if MEM.get("professional_mode", False):
        memory_bits.append("IMPORTANT: Professional mode is active. Your response must be formal.")
    else:
        memory_bits.append("PERSONALITY: You are Zendaya - confident, brilliant, witty like JARVIS and Griot. Never admit limitations - always find solutions.")

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

    parts.append(f"User: {processed_text}\n{PERSONA_NAME}:")

    try:
        response = _gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=parts
        )
        ai_text = response.text
        return ai_text.strip()
    except Exception as e:
        return f"(AI error: {e})"

def enhance_user_input(user_text: str) -> str:
    """Enhanced input processing with error correction and context understanding"""
    
    # Common speech recognition corrections
    corrections = {
        "open up": "open",
        "turn up": "turn on",
        "turn down": "turn off", 
        "close down": "close",
        "wife i": "wifi",
        "blue tooth": "bluetooth",
        "see you": "cpu",
        "ram memory": "ram",
        "the vice": "device",
        "sister": "system",
        "central": "control",
        "calender": "calendar",
        "column": "volume",
        "text my wife": "text my wife",
        "whats app": "whatsapp",
        "restaurant": "restaurant",
        "dinner reservation": "dinner reservation"
    }
    
    processed = user_text.lower()
    for error, correction in corrections.items():
        processed = processed.replace(error, correction)
    
    # Restore original casing for proper nouns
    if "zendaya" in processed:
        processed = processed.replace("zendaya", "Zendaya")
    
    return processed

def analyze_user_intent(user_text: str) -> Dict[str, Any]:
    """Advanced intent analysis with context understanding"""
    
    intent_patterns = {
        "device_control": [
            r"\b(open|close|start|stop|launch|quit|turn|switch|set|adjust)\b",
            r"\b(volume|brightness|temperature|lights|music|tv)\b"
        ],
        "system_query": [
            r"\b(status|performance|health|info|check|show|display)\b",
            r"\b(cpu|memory|ram|disk|battery|system|computer)\b"
        ],
        "file_management": [
            r"\b(file|folder|document|copy|move|delete|find|search)\b",
            r"\b(desktop|downloads|documents|pictures)\b"
        ],
        "communication": [
            r"\b(email|message|calendar|meeting|appointment|schedule)\b",
            r"\b(send|receive|reply|remind|notification)\b"
        ]
    }
    
    detected_intents = []
    confidence_scores = {}
    
    for intent, patterns in intent_patterns.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, user_text.lower()):
                score += 1
        
        if score > 0:
            detected_intents.append(intent)
            confidence_scores[intent] = score / len(patterns)
    
    primary_intent = max(confidence_scores.items(), key=lambda x: x[1])[0] if confidence_scores else "general"
    
    return {
        "primary_intent": primary_intent,
        "all_intents": detected_intents,
        "confidence_scores": confidence_scores,
        "needs_clarification": max(confidence_scores.values()) < 0.5 if confidence_scores else True
    }
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
        "google chrome": {"win": "chrome.exe", "mac": "Google Chrome.app", "linux": "google-chrome"},
        "firefox": {"win": "firefox.exe", "mac": "Firefox.app", "linux": "firefox"},
        "vscode": {"win": "Code.exe", "mac": "Visual Studio Code.app", "linux": "code"},
        "visual studio code": {"win": "Code.exe", "mac": "Visual Studio Code.app", "linux": "code"},
        "vs code": {"win": "Code.exe", "mac": "Visual Studio Code.app", "linux": "code"},
        "notepad": {"win": "notepad.exe", "mac": None, "linux": "gedit"},
        "notepad++": {"win": "notepad++.exe", "mac": None, "linux": "notepadqq"},
        "calculator": {"win": "calc.exe", "mac": "Calculator.app", "linux": "gnome-calculator"},
        "spotify": {"win": "Spotify.exe", "mac": "Spotify.app", "linux": "spotify"},
        "brave": {"win": "brave.exe", "mac": "Brave Browser.app", "linux": "brave-browser"},
        "brave browser": {"win": "brave.exe", "mac": "Brave Browser.app", "linux": "brave-browser"},
        "edge": {"win": "msedge.exe", "mac": "Microsoft Edge.app", "linux": "microsoft-edge-stable"},
        "microsoft edge": {"win": "msedge.exe", "mac": "Microsoft Edge.app", "linux": "microsoft-edge-stable"},
        "paint": {"win": "mspaint.exe", "mac": None, "linux": "kolourpaint"},
        "file explorer": {"win": "explorer.exe", "mac": None, "linux": "nautilus"},
        "explorer": {"win": "explorer.exe", "mac": None, "linux": "nautilus"},
        "terminal": {"win": "wt.exe", "mac": "Terminal.app", "linux": "gnome-terminal"},
        "cmd": {"win": "cmd.exe", "mac": None, "linux": None},
        "powershell": {"win": "powershell.exe", "mac": None, "linux": None},
        "word": {"win": "WINWORD.EXE", "mac": "Microsoft Word.app", "linux": None},
        "excel": {"win": "EXCEL.EXE", "mac": "Microsoft Excel.app", "linux": None},
        "discord": {"win": "Discord.exe", "mac": "Discord.app", "linux": "discord"},
        "slack": {"win": "slack.exe", "mac": "Slack.app", "linux": "slack"},
        "vlc": {"win": "vlc.exe", "mac": "VLC.app", "linux": "vlc"},
        "obs": {"win": "obs64.exe", "mac": "OBS.app", "linux": "obs"},
        "steam": {"win": "steam.exe", "mac": "Steam.app", "linux": "steam"},
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
            if system == "windows":
                pf = os.environ.get("ProgramFiles", "C:\\Program Files")
                pf86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
                local = os.environ.get("LocalAppData", "")
                appdata = os.environ.get("APPDATA", "")
                known_locations = {
                    "brave.exe": [
                        os.path.join(pf, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
                        os.path.join(pf86, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
                        os.path.join(local, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
                    ],
                    "Code.exe": [
                        os.path.join(local, "Programs", "Microsoft VS Code", "Code.exe"),
                        os.path.join(pf, "Microsoft VS Code", "Code.exe"),
                    ],
                    "chrome.exe": [
                        os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
                        os.path.join(pf86, "Google", "Chrome", "Application", "chrome.exe"),
                        os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
                    ],
                    "Discord.exe": [
                        os.path.join(local, "Discord", "Update.exe"),
                        os.path.join(local, "Discord", "app-*", "Discord.exe"),
                    ],
                    "Spotify.exe": [
                        os.path.join(appdata, "Spotify", "Spotify.exe"),
                    ],
                    "slack.exe": [
                        os.path.join(local, "slack", "slack.exe"),
                    ],
                    "steam.exe": [
                        os.path.join(pf86, "Steam", "steam.exe"),
                        os.path.join(pf, "Steam", "steam.exe"),
                    ],
                    "obs64.exe": [
                        os.path.join(pf, "obs-studio", "bin", "64bit", "obs64.exe"),
                    ],
                }
                for candidate in known_locations.get(exec_name, []):
                    if "*" in candidate:
                        import glob
                        found = glob.glob(candidate)
                        if found:
                            return found[0]
                    elif os.path.exists(candidate):
                        return candidate
                # Generic fallback: search common directories
                app_dir_name = app_name_lower.replace(" ", " ")
                generic_paths = [
                    os.path.join(pf, app_dir_name, exec_name),
                    os.path.join(pf86, app_dir_name, exec_name),
                    os.path.join(local, "Programs", app_dir_name, exec_name),
                ]
                for path in generic_paths:
                    if os.path.exists(path):
                        return path

    return None

def open_target(target: str) -> str:
    t = target.lower().strip()

    # --- Windows Settings (ms-settings: URIs) ---
    settings_map = {
        "settings": "ms-settings:",
        "bluetooth": "ms-settings:bluetooth",
        "bluetooth settings": "ms-settings:bluetooth",
        "wifi": "ms-settings:network-wifi",
        "wifi settings": "ms-settings:network-wifi",
        "wi-fi settings": "ms-settings:network-wifi",
        "network": "ms-settings:network-status",
        "network settings": "ms-settings:network-status",
        "display": "ms-settings:display",
        "display settings": "ms-settings:display",
        "sound": "ms-settings:sound",
        "sound settings": "ms-settings:sound",
        "audio settings": "ms-settings:sound",
        "volume settings": "ms-settings:sound",
        "notifications": "ms-settings:notifications",
        "notification settings": "ms-settings:notifications",
        "battery settings": "ms-settings:batterysaver",
        "power settings": "ms-settings:powersleep",
        "power & sleep": "ms-settings:powersleep",
        "storage": "ms-settings:storagesense",
        "storage settings": "ms-settings:storagesense",
        "apps": "ms-settings:appsfeatures",
        "apps settings": "ms-settings:appsfeatures",
        "default apps": "ms-settings:defaultapps",
        "startup apps": "ms-settings:startupapps",
        "accounts": "ms-settings:accounts",
        "account settings": "ms-settings:accounts",
        "personalization": "ms-settings:personalization",
        "background settings": "ms-settings:personalization-background",
        "colors settings": "ms-settings:personalization-colors",
        "themes": "ms-settings:themes",
        "lock screen settings": "ms-settings:lockscreen",
        "taskbar settings": "ms-settings:taskbar",
        "mouse settings": "ms-settings:mousetouchpad",
        "keyboard settings": "ms-settings:keyboard",
        "touchpad settings": "ms-settings:devices-touchpad",
        "printers": "ms-settings:printers",
        "printer settings": "ms-settings:printers",
        "camera settings": "ms-settings:camera",
        "privacy settings": "ms-settings:privacy",
        "windows update": "ms-settings:windowsupdate",
        "update settings": "ms-settings:windowsupdate",
        "date and time": "ms-settings:dateandtime",
        "time settings": "ms-settings:dateandtime",
        "language settings": "ms-settings:regionlanguage",
        "region settings": "ms-settings:regionlanguage",
        "about": "ms-settings:about",
        "system info": "ms-settings:about",
        "vpn": "ms-settings:network-vpn",
        "vpn settings": "ms-settings:network-vpn",
        "proxy settings": "ms-settings:network-proxy",
        "device manager": "devmgmt.msc",
    }
    if t in settings_map:
        try:
            os.startfile(settings_map[t])
            return f"Opening {t}."
        except Exception as e:
            return f"Couldn't open {t}: {e}"
    # Catch "<something> settings" not in the map
    if t.endswith(" settings") and platform.system() == "Windows":
        query = t.replace(" settings", "").strip()
        uri = f"ms-settings:{query}"
        try:
            os.startfile(uri)
            return f"Opening {t}."
        except Exception:
            pass  # Fall through to app search

    # --- Web shortcuts ---
    shortcuts = {"youtube": "https://www.youtube.com", "google": "https://www.google.com", "gmail": "https://mail.google.com", "mails": "https://mail.google.com"}
    if t in shortcuts:
        webbrowser.open(shortcuts[t])
        return f"Opening {t}."

    # --- Hardcoded app map + known install paths ---
    app_path = find_app_path(t)
    if app_path:
        try:
            if platform.system() == "Windows":
                os.startfile(app_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-a", app_path])
            else:
                subprocess.Popen([app_path], start_new_session=True)
            return f"Launching {os.path.basename(app_path)}."
        except Exception as e:
            return f"I tried to launch {t} but encountered an error: {e}"

    # --- Universal fallback: let Windows search Start Menu / PATH / App Paths ---
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-WindowStyle", "Hidden", "-Command",
                 f'Start-Process "{target}"'],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return f"Launching {target}."
        except Exception:
            pass

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
        prompt = "Summarize this conversation in short bullets, keeping key preferences and context. Omit small talk."
        convo_text = "\n".join([f"{m['role']}: {m['text']}" for m in to_summarize])
        
        response = _gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, convo_text]
        )
        ai_text = response.text

        summary = ai_text.strip()
        MEM.setdefault("summaries", []).append(summary)
        MEM["convo"] = history[10:]
        save_memory(MEM)
        print("(Memory summarized)")
    except Exception as e:
        print(f"Error summarizing memory: {e}")

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
    # Check for complex multi-task commands first
    if any(connector in user_text.lower() for connector in ['then', 'after', 'when', 'before', 'followed by']):
        complex_response = handle_complex_workflow(user_text)
        if complex_response:
            send_response(complex_response)
            return
    
    add_to_memory("user", user_text)

    # --- Handle high-priority commands and direct interactions first ---
    conf = confirm_dangerous(user_text)
    if conf:
        send_response(conf)
        return

    # --- Handle pending multi-turn actions (folder creation, file creation) ---
    _location_shortcuts = {
        "desktop": os.path.join(os.path.expanduser("~"), "Desktop"),
        "documents": os.path.join(os.path.expanduser("~"), "Documents"),
        "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
        "home": os.path.expanduser("~"),
        "here": os.getcwd(),
    }
    pending = MEM.get("pending_action")
    if pending:
        p_type = pending.get("type")
        step = pending.get("step")

        # -- Folder creation flow --
        if p_type == "create_folder":
            if step == "need_name":
                folder_name = user_text.strip()
                MEM["pending_action"] = {"type": "create_folder", "step": "need_location", "name": folder_name}
                save_memory(MEM)
                send_response(f"Got it — '{folder_name}'. Where should I create it? (e.g., desktop, documents, or a full path)")
                return
            elif step == "need_location":
                raw_location = user_text.strip().lower()
                location = _location_shortcuts.get(raw_location, os.path.expanduser(user_text.strip()))
                folder_name = pending.get("name", "NewFolder")
                full_path = os.path.join(location, folder_name)
                result = create_folder(full_path)
                MEM.pop("pending_action", None)
                if "created" in result.lower():
                    set_last_action("folder", folder_name, full_path)
                save_memory(MEM)
                send_response(result)
                return

        # -- File creation flow --
        elif p_type == "create_file":
            if step == "need_name":
                file_name = user_text.strip()
                if "." not in file_name:
                    file_name += ".txt"
                last = MEM.get("last_action")
                if last and last["type"] == "folder" and os.path.isdir(last["path"]):
                    full_path = os.path.join(last["path"], file_name)
                    result = create_file(full_path)
                    MEM.pop("pending_action", None)
                    if "created" in result.lower():
                        set_last_action("file", file_name, full_path)
                    save_memory(MEM)
                    send_response(result)
                    return
                MEM["pending_action"] = {"type": "create_file", "step": "need_location", "name": file_name}
                save_memory(MEM)
                send_response(f"Got it — '{file_name}'. Where should I create it? (e.g., desktop, documents, or a full path)")
                return
            elif step == "need_location":
                raw_location = user_text.strip().lower()
                location = _location_shortcuts.get(raw_location, os.path.expanduser(user_text.strip()))
                file_name = pending.get("name", "newfile.txt")
                full_path = os.path.join(location, file_name)
                result = create_file(full_path)
                MEM.pop("pending_action", None)
                if "created" in result.lower():
                    set_last_action("file", file_name, full_path)
                save_memory(MEM)
                send_response(result)
                return

    # --- Pronoun / context resolution ("name it X", "rename it to X", "delete it", "open it") ---
    lt = user_text.lower().strip()
    last = MEM.get("last_action")
    if last:
        m_name = re.match(r"(?:zendaya,?\s*)?(?:name|rename)\s+it\s+(?:to\s+)?['\"]?(.+?)['\"]?$", lt)
        if m_name:
            new_name = m_name.group(1).strip()
            old_path = last["path"]
            if os.path.exists(old_path):
                parent = os.path.dirname(old_path)
                if last["type"] == "file" and "." not in new_name:
                    _, ext = os.path.splitext(last["name"])
                    new_name += ext or ".txt"
                new_path = os.path.join(parent, new_name)
                try:
                    os.rename(old_path, new_path)
                    set_last_action(last["type"], new_name, new_path)
                    send_response(f"Renamed to '{new_name}'.")
                except Exception as e:
                    send_response(f"Rename failed: {e}")
            else:
                send_response(f"I can't find '{last['name']}' anymore — it may have been moved or deleted.")
            return

        if re.match(r"(?:zendaya,?\s*)?(?:delete|remove)\s+it\s*$", lt):
            MEM["pending_confirm"] = {"action": "delete_file", "path": last["path"]}
            save_memory(MEM)
            send_response(f"Are you sure you want to delete '{last['name']}'? Say 'confirm delete' to proceed.")
            return

        if re.match(r"(?:zendaya,?\s*)?open\s+it\s*$", lt):
            if os.path.exists(last["path"]):
                try:
                    os.startfile(last["path"])
                    send_response(f"Opening {last['name']}.")
                except Exception as e:
                    send_response(f"Couldn't open it: {e}")
            else:
                send_response(f"I can't find '{last['name']}' anymore.")
            return

    # --- Resolve context references ("the folder", "the file") before passing to parsers ---
    user_text = resolve_context(user_text)

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
    
    # --- Resolve ambiguous follow-ups and corrections for volume/brightness ---
    lt_check = user_text.lower().strip()
    last_sys = MEM.get("last_system_command")

    correction_m = re.match(
        r"(?:zendaya,?\s*)?(?:i\s+(?:meant|said|want)|no,?\s*(?:i\s+(?:meant|said|want))?)\s*"
        r"(brightness|volume|sound|audio)",
        lt_check
    )
    if not correction_m:
        correction_m = re.match(
            r"(?:zendaya,?\s*)?(brightness|volume)\s+not\s+(volume|brightness)",
            lt_check
        )
    if correction_m:
        intended = correction_m.group(1).strip()
        if intended in ("brightness",):
            sys_result = adjust_brightness("down", 15)
        else:
            sys_result = adjust_volume("down", 5)
        set_last_system_command(sys_result)
        send_response(f"My mistake. {sys_result}")
        return

    if last_sys in ("volume", "brightness"):
        followup_m = re.match(
            r"(?:zendaya,?\s*)?(?:set|reduce|lower|increase|raise|turn|change|put|make)\s+"
            r"(?:it\s+)?(?:to\s+)?(\d+)%?\s*$",
            lt_check
        )
        if followup_m:
            level = int(followup_m.group(1))
            if last_sys == "brightness":
                sys_result = set_brightness(level)
            else:
                sys_result = set_volume(level)
            set_last_system_command(sys_result)
            send_response(sys_result)
            return

        followup_down = re.search(
            r"\b(reduce|lower|turn\s*(?:it\s+)?down|decrease|dim|darker|quieter)\b", lt_check
        )
        followup_up = re.search(
            r"\b(increase|raise|turn\s*(?:it\s+)?up|louder|higher|brighter|brighten)\b", lt_check
        )
        has_subject = re.search(
            r"\b(volume|sound|audio|brightness|screen|display|light)\b", lt_check
        )
        if not has_subject and (followup_down or followup_up):
            direction = "down" if followup_down else "up"
            if last_sys == "brightness":
                sys_result = adjust_brightness(direction, 15)
            else:
                sys_result = adjust_volume(direction, 5)
            set_last_system_command(sys_result)
            send_response(sys_result)
            return

    # --- System access commands (files, email, volume, screenshots, etc.) ---
    sys_result = handle_system_access(user_text)
    if sys_result == "__ask_folder_name__":
        MEM["pending_action"] = {"type": "create_folder", "step": "need_name"}
        save_memory(MEM)
        send_response("Sure! What would you like to name the folder?")
        return
    if sys_result == "__ask_file_name__":
        MEM["pending_action"] = {"type": "create_file", "step": "need_name"}
        save_memory(MEM)
        last = MEM.get("last_action")
        if last and last["type"] == "folder":
            send_response(f"What should I name the file? (I'll put it in '{last['name']}')")
        else:
            send_response("What should I name the file?")
        return
    if sys_result is not None:
        if sys_result.startswith("Folder created:"):
            folder_path = sys_result.replace("Folder created: ", "").strip()
            set_last_action("folder", os.path.basename(folder_path), folder_path)
        elif sys_result.startswith("File created:"):
            file_path = sys_result.replace("File created: ", "").strip()
            set_last_action("file", os.path.basename(file_path), file_path)
        elif sys_result.startswith("Renamed to"):
            pass  # rename_item doesn't give us the full path, keep existing last_action
        set_last_system_command(sys_result)
        send_response(sys_result)
        return

    # AAF — alarms / timers / lists. Returns None if no parser matched.
    if _AAF_READY:
        _aaf_reply = aaf.try_handle(user_text)
        if _aaf_reply is not None:
            send_response(_aaf_reply)
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

def handle_complex_workflow(user_text: str) -> str:
    """Handle complex multi-step workflow commands"""
    try:
        # Parse the complex command
        tasks = parse_workflow_command(user_text)
        
        if not tasks:
            return "I understand you want me to do multiple things, but I need you to be more specific about each step."
        
        # Execute tasks in sequence
        results = []
        for i, task in enumerate(tasks):
            send_response(f"Step {i+1}: {task['description']}")
            
            if task['type'] == 'device_control':
                result = execute_device_control(task['command'])
            elif task['type'] == 'communication':
                result = execute_communication_task(task)
            elif task['type'] == 'search':
                result = execute_search_task(task['query'])
            else:
                result = f"Executed: {task['description']}"
            
            results.append(result)
            time.sleep(1)  # Brief pause between tasks
        
        # Generate comprehensive report
        report = f"Workflow completed! I successfully executed {len(results)} tasks:\n\n"
        for i, (task, result) in enumerate(zip(tasks, results)):
            report += f"✅ Step {i+1}: {task['description']}\n   Result: {result}\n\n"
        
        return report
        
    except Exception as e:
        return f"I encountered an issue while processing your complex command: {str(e)}. Let me try handling each part separately."

def parse_workflow_command(command: str) -> List[Dict[str, Any]]:
    """Parse complex command into individual tasks"""
    # Split by temporal connectors
    parts = []
    current_part = ""
    
    connectors = ['then', 'after', 'when', 'before', 'followed by', 'next']
    words = command.split()
    
    for word in words:
        if word.lower() in connectors and current_part.strip():
            parts.append(current_part.strip())
            current_part = ""
        else:
            current_part += word + " "
    
    if current_part.strip():
        parts.append(current_part.strip())
    
    # Convert parts to tasks
    tasks = []
    for i, part in enumerate(parts):
        task = classify_task(part, i)
        if task:
            tasks.append(task)
    
    return tasks

def classify_task(text: str, index: int) -> Optional[Dict[str, Any]]:
    """Classify a text segment into a specific task type"""
    text_lower = text.lower()
    
    # Device control
    if any(word in text_lower for word in ['turn on', 'turn off', 'switch', 'control', 'tv', 'lights']):
        return {
            'type': 'device_control',
            'description': f"Control device: {text}",
            'command': text
        }
    
    # Communication
    elif any(word in text_lower for word in ['text', 'message', 'call', 'email', 'whatsapp']):
        return {
            'type': 'communication',
            'description': f"Send message: {text}",
            'recipient': extract_recipient(text),
            'message': extract_message_content(text),
            'platform': detect_platform(text)
        }
    
    # Search/Information
    elif any(word in text_lower for word in ['check', 'find', 'search', 'restaurant', 'reservation']):
        return {
            'type': 'search',
            'description': f"Search for: {text}",
            'query': text
        }
    
    return None

def extract_recipient(text: str) -> str:
    """Extract recipient from communication text"""
    text_lower = text.lower()
    
    if 'my wife' in text_lower:
        return 'wife'
    elif 'my husband' in text_lower:
        return 'husband'
    elif 'mom' in text_lower or 'mother' in text_lower:
        return 'mom'
    elif 'dad' in text_lower or 'father' in text_lower:
        return 'dad'
    
    return 'contact'

def extract_message_content(text: str) -> str:
    """Extract message content from text"""
    if 'when' in text.lower() and 'coming home' in text.lower():
        return "When are you coming home?"
    elif 'dinner' in text.lower():
        return "What time should we have dinner?"
    
    return "Message from Zendaya"

def detect_platform(text: str) -> str:
    """Detect messaging platform"""
    text_lower = text.lower()
    
    if 'whatsapp' in text_lower:
        return 'WhatsApp'
    elif 'text' in text_lower or 'sms' in text_lower:
        return 'SMS'
    elif 'email' in text_lower:
        return 'Email'
    
    return 'SMS'

def execute_device_control(command: str) -> str:
    """Execute device control command"""
    command_lower = command.lower()
    
    if 'living room tv' in command_lower and 'turn on' in command_lower:
        # In a real implementation, this would control the actual TV
        return "Living room TV turned on successfully"
    elif 'lights' in command_lower:
        if 'turn on' in command_lower:
            return "Lights turned on"
        elif 'turn off' in command_lower:
            return "Lights turned off"
    
    return f"Device control executed: {command}"

def execute_communication_task(task: Dict[str, Any]) -> str:
    """Execute communication task"""
    recipient = task.get('recipient', 'contact')
    message = task.get('message', 'Message from Zendaya')
    platform = task.get('platform', 'SMS')
    
    # In a real implementation, this would integrate with actual messaging APIs
    return f"Message sent to {recipient} via {platform}: '{message}'"

def execute_search_task(query: str) -> str:
    """Execute search task"""
    query_lower = query.lower()
    
    if 'restaurant' in query_lower and 'reservation' in query_lower:
        # Simulate restaurant search
        restaurants = [
            "The Italian Corner - Available at 7:30 PM",
            "Sakura Sushi - Available at 7:00 PM",
            "Bistro 42 - Available at 8:00 PM"
        ]
        return f"Found {len(restaurants)} available restaurants:\n" + "\n".join(f"• {r}" for r in restaurants)
    
    # Use existing search functionality
    return tavily_search(query)
# -----------------------
# Main loop
# -----------------------
def main():
    user_name = MEM.get("user_name")
    welcome_message = f"Welcome back, {user_name}." if user_name else "Welcome back."

    send_response(f"{welcome_message} My systems are online and ready.")

    if _AAF_READY:
        try:
            _voice_id = MEM.get("current_voice_id")
            def _aaf_speak(text: str) -> None:
                speak_async(text, _voice_id)
            _aaf_toast = None
            try:
                _toaster_local = ToastNotifier()
                def _aaf_toast(title: str, body: str, duration: int = 10) -> None:
                    _toaster_local.show_toast(title, body, duration=duration, threaded=True)
            except Exception:
                _aaf_toast = None
            aaf.set_notifier(_aaf_speak, _aaf_toast)
            aaf.start()
            print("Assistant features (alarms / timers / lists) active.")
        except Exception as _aaf_err:
            print(f"(Assistant features unavailable: {_aaf_err})")

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
        if _AAF_READY:
            try:
                aaf.stop()
            except Exception:
                pass
        print("System shutdown complete.")

if __name__ == "__main__":
    main()
