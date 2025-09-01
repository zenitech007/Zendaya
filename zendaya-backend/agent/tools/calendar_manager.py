"""
Calendar Management Tool - Google Calendar integration
"""
import os
from typing import Dict, Any
from datetime import datetime, timezone
from langchain.tools import Tool
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

class CalendarTool:
    def __init__(self):
        self.credentials_path = "credentials.json"
        self.token_path = "token_calendar.json"
    
    def check_calendar(self, query: str = "") -> str:
        """Check upcoming calendar events"""
        try:
            service = self._get_calendar_service()
            if not service:
                return "Calendar service unavailable - authentication required"
            
            # Get upcoming events
            now = datetime.now(timezone.utc).isoformat()
            events_result = service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=5,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                return "No upcoming events found."
            
            event_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                summary = event.get('summary', 'No title')
                event_list.append(f"- {summary} at {start}")
            
            return f"Upcoming events:\n" + "\n".join(event_list)
            
        except Exception as e:
            return f"Calendar error: {str(e)}"
    
    def _get_calendar_service(self):
        """Get authenticated Google Calendar service"""
        # This is a simplified version - in production you'd handle OAuth flow properly
        if not os.path.exists(self.credentials_path):
            return None
        
        try:
            # Load existing token or create new one
            creds = None
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path)
            
            if creds and creds.valid:
                return build('calendar', 'v3', credentials=creds)
            
        except Exception as e:
            print(f"Calendar authentication error: {e}")
        
        return None
    
    def get_tool(self) -> Tool:
        """Return LangChain tool"""
        return Tool(
            name="calendar_check",
            description="Check upcoming calendar events and appointments",
            func=self.check_calendar
        )