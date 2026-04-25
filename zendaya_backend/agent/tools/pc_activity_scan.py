"""
Zendaya AI - PC Activity Scanner & Summarizer Tool
--------------------------------------------------
This tool gives Zendaya the ability to understand the user's recent activity
on their local machine, enabling proactive and context-aware interactions.
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
import asyncio

# Assuming Gemini service is available in your project structure
from zendaya_backend.ai_core.gemini_service import GeminiService

# --- Configuration ---
# Directories to scan for recent user activity
SCAN_DIRECTORIES = {
    "Documents": Path.home() / "Documents",
    "Desktop": Path.home() / "Desktop",
    "Downloads": Path.home() / "Downloads",
}
# How far back to look for file modifications (in hours)
RECENCY_THRESHOLD_HOURS = 24
# Maximum number of files to consider for summary to avoid overwhelming the AI
MAX_FILES_TO_SUMMARIZE = 15
# File extensions to ignore
IGNORED_EXTENSIONS = {'.tmp', '.log', '.bak', '.part', '.crdownload'}

async def scan_and_summarize_activity() -> Dict[str, Any]:
    """
    Scans the user's PC for recent file activity and generates an AI-powered summary.

    Returns:
        A dictionary containing the summary and a list of recent files,
        or an empty dictionary if no significant activity is found.
    """
    print("🧠 [Zendaya] Analyzing recent user activity...")
    recent_files = []
    now = datetime.now()
    time_threshold = now - timedelta(hours=RECENCY_THRESHOLD_HOURS)

    for name, dir_path in SCAN_DIRECTORIES.items():
        if not dir_path.exists():
            continue

        try:
            for entry in os.scandir(dir_path):
                if entry.is_file():
                    path = Path(entry.path)
                    if path.suffix.lower() in IGNORED_EXTENSIONS:
                        continue
                    
                    try:
                        modified_time = datetime.fromtimestamp(entry.stat().st_mtime)
                        if modified_time > time_threshold:
                            recent_files.append({
                                "name": entry.name,
                                "path": entry.path,
                                "modified": modified_time,
                                "location": name
                            })
                    except FileNotFoundError:
                        # File might have been deleted between scandir and stat
                        continue
        except OSError as e:
            print(f"⚠️  Could not scan directory '{dir_path}': {e}")


    if not recent_files:
        print("└── No significant recent activity found.")
        return {}

    # Sort files by most recently modified
    recent_files.sort(key=lambda x: x["modified"], reverse=True)
    
    # Limit the number of files for the summary prompt
    files_for_summary = recent_files[:MAX_FILES_TO_SUMMARIZE]

    # --- Generate AI Summary ---
    try:
        gemini = GeminiService()
        if not gemini.is_ready():
            raise ConnectionError("Gemini service is not available for summarization.")

        file_list_str = "\n".join(
            f"- '{f['name']}' in '{f['location']}' (last touched: {f['modified'].strftime('%I:%M %p')})"
            for f in files_for_summary
        )

        prompt = f"""
        As an AI assistant, analyze the following list of recently modified files on the user's PC.
        Based on these file names, generate a concise, one-sentence summary of the user's likely last work session.
        Infer the main activity (e.g., "working on a project," "managing finances," "designing graphics").
        
        Example:
        Files:
        - 'Q3_Report_Final.docx' in 'Documents'
        - 'sales_data.xlsx' in 'Downloads'
        - 'presentation_slides_v2.pptx' in 'Desktop'
        Summary: It looks like you were recently focused on preparing a report and presentation, likely related to Q3 sales.

        Here is the user's recent file activity:
        {file_list_str}

        Generate the summary now:
        """

        summary = await gemini.generate_response(prompt)
        
        print(f"└── Activity Summary: {summary}")
        
        return {
            "summary": summary,
            "recent_files": [f["name"] for f in files_for_summary]
        }

    except Exception as e:
        print(f"⚠️  Failed to generate activity summary: {e}")
        return {
            "summary": "I've noted some recent file activity, but couldn't generate a summary.",
            "recent_files": [f["name"] for f in files_for_summary]
        }
