"""
Google API Manager for Jarvis.
Autonomous management of Google services.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import google_integration, context_manager, providers

ROOT = Path(__file__).resolve().parents[1]
GOOGLE_DATA_PATH = ROOT / "data" / "google_data"
DRIVE_SYNC_PATH = GOOGLE_DATA_PATH / "drive"
GMAIL_SYNC_PATH = GOOGLE_DATA_PATH / "gmail"
CALENDAR_SYNC_PATH = GOOGLE_DATA_PATH / "calendar"


class GoogleManager:
    """Manages autonomous operations with Google services."""
    
    def __init__(self):
        self.integration = google_integration.get_google_integration()
        self.ensure_directories()
        
    def ensure_directories(self):
        """Ensure data directories exist."""
        for path in [GOOGLE_DATA_PATH, DRIVE_SYNC_PATH, GMAIL_SYNC_PATH, CALENDAR_SYNC_PATH]:
            path.mkdir(parents=True, exist_ok=True)
    
    def sync_drive(self, folder_id: str = "root", max_files: int = 100) -> Dict[str, Any]:
        """Sync Google Drive files locally."""
        service = self.integration.get_service("drive")
        if not service:
            return {"success": False, "error": "Drive service not available"}
        
        try:
            # List files
            results = service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                pageSize=max_files,
                fields="files(id,name,mimeType,createdTime,modifiedTime,size,webViewLink)"
            ).execute()
            
            files = results.get("files", [])
            synced = 0
            
            for file in files:
                # Skip Google Docs/Sheets for now (need special handling)
                if file["mimeType"].startswith("application/vnd.google-apps"):
                    continue
                
                # Download file
                file_path = DRIVE_SYNC_PATH / file["name"]
                
                # Skip if exists and is recent
                if file_path.exists():
                    local_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    remote_time = datetime.fromisoformat(file["modifiedTime"].replace("Z", "+00:00"))
                    if local_time >= remote_time:
                        continue
                
                # Download
                request = service.files().get_media(fileId=file["id"])
                with open(file_path, "wb") as f:
                    f.write(request.execute())
                
                # Set modification time
                remote_time = datetime.fromisoformat(file["modifiedTime"].replace("Z", "+00:00"))
                timestamp = remote_time.timestamp()
                file_path.touch()
                import os
                os.utime(file_path, (timestamp, timestamp))
                
                synced += 1
                time.sleep(0.1)  # Rate limit
            
            return {
                "success": True,
                "files_found": len(files),
                "files_synced": synced
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def scan_gmail(self, max_emails: int = 50) -> Dict[str, Any]:
        """Scan Gmail for important information."""
        service = self.integration.get_service("gmail")
        if not service:
            return {"success": False, "error": "Gmail service not available"}
        
        try:
            # Get recent messages
            results = service.users().messages().list(
                userId="me",
                maxResults=max_emails,
                q="is:unread OR (subject:important OR subject:urgent OR subject:action required)"
            ).execute()
            
            messages = results.get("messages", [])
            important_info = []
            
            for msg in messages:
                # Get full message
                message = service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From", "Date", "X-Priority"]
                ).execute()
                
                # Extract headers
                headers = {h["name"]: h["value"] for h in message["payload"].get("headers", [])}
                
                # Check if important
                priority = headers.get("X-Priority", "").lower()
                subject = headers.get("Subject", "").lower()
                
                if any(keyword in subject for keyword in ["urgent", "important", "action", "asap"]) or \
                   priority in ["1", "high"]:
                    
                    important_info.append({
                        "id": msg["id"],
                        "subject": headers.get("Subject", ""),
                        "from": headers.get("From", ""),
                        "date": headers.get("Date", ""),
                        "snippet": message.get("snippet", "")
                    })
            
            # Save to context
            if important_info:
                ctx = context_manager.load_master_context()
                ctx.emails.extend(important_info[:5])  # Keep last 5
                context_manager.save_master_context(ctx)
            
            return {
                "success": True,
                "messages_scanned": len(messages),
                "important_found": len(important_info),
                "important_emails": important_info
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def sync_calendar(self, days_ahead: int = 7) -> Dict[str, Any]:
        """Sync Google Calendar events."""
        service = self.integration.get_service("calendar")
        if not service:
            return {"success": False, "error": "Calendar service not available"}
        
        try:
            # Get primary calendar
            calendar_id = "primary"
            
            # Time range
            now = datetime.utcnow()
            end_time = now + timedelta(days=days_ahead)
            
            # List events
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=now.isoformat() + "Z",
                timeMax=end_time.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime",
                maxResults=50
            ).execute()
            
            events = events_result.get("items", [])
            upcoming = []
            
            for event in events:
                event_data = {
                    "id": event["id"],
                    "summary": event.get("summary", "No title"),
                    "start": event["start"].get("dateTime", event["start"].get("date")),
                    "end": event["end"].get("dateTime", event["end"].get("date")),
                    "location": event.get("location", ""),
                    "description": event.get("description", "")[:200]
                }
                upcoming.append(event_data)
            
            # Save to context
            if upcoming:
                ctx = context_manager.load_master_context()
                ctx.calendar_events = upcoming
                context_manager.save_master_context(ctx)
            
            return {
                "success": True,
                "events_found": len(events),
                "upcoming_events": upcoming
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_document(self, title: str, content: str, folder_id: str = None) -> Dict[str, Any]:
        """Create a Google Doc."""
        service = self.integration.get_service("docs")
        drive_service = self.integration.get_service("drive")
        
        if not service or not drive_service:
            return {"success": False, "error": "Docs/Drive service not available"}
        
        try:
            # Create document
            doc = service.documents().create(
                body={"title": title}
            ).execute()
            
            doc_id = doc["documentId"]
            
            # Add content (simplified - would need more complex structure for rich text)
            requests = [
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": content
                    }
                }
            ]
            
            service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": requests}
            ).execute()
            
            # Move to folder if specified
            if folder_id:
                drive_service.files().update(
                    fileId=doc_id,
                    addParents=folder_id,
                    fields="id, parents"
                ).execute()
            
            return {
                "success": True,
                "document_id": doc_id,
                "document_url": f"https://docs.google.com/document/d/{doc_id}"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def send_email(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """Send an email via Gmail."""
        service = self.integration.get_service("gmail")
        if not service:
            return {"success": False, "error": "Gmail service not available"}
        
        try:
            import base64
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Create message
            message = MIMEMultipart()
            message["to"] = to
            message["subject"] = subject
            message.attach(MIMEText(body, "plain"))
            
            # Encode
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Send
            result = service.users().messages().send(
                userId="me",
                body={"raw": raw}
            ).execute()
            
            return {
                "success": True,
                "message_id": result["id"]
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def analyze_drive_content(self) -> Dict[str, Any]:
        """Analyze Drive content for insights."""
        service = self.integration.get_service("drive")
        if not service:
            return {"success": False, "error": "Drive service not available"}
        
        try:
            # Get file statistics
            results = service.files().list(
                q="trashed=false",
                pageSize=1000,
                fields="files(name,mimeType,size,createdTime,modifiedTime)"
            ).execute()
            
            files = results.get("files", [])
            
            # Analyze
            total_size = 0
            file_types = {}
            recent_files = []
            
            cutoff = datetime.now() - timedelta(days=7)
            
            for file in files:
                # Size
                if "size" in file:
                    total_size += int(file["size"])
                
                # Type
                mime = file["mimeType"]
                if mime not in file_types:
                    file_types[mime] = 0
                file_types[mime] += 1
                
                # Recent files
                created = datetime.fromisoformat(file["createdTime"].replace("Z", "+00:00"))
                if created > cutoff:
                    recent_files.append({
                        "name": file["name"],
                        "type": mime,
                        "created": file["createdTime"]
                    })
            
            # Generate insights with LLM
            insights = []
            if recent_files:
                prompt = f"""Analyze these recent Google Drive files for patterns:

Recent Files:
{json.dumps(recent_files[:10], indent=2)}

File Types:
{json.dumps(file_types, indent=2)}

Provide insights about:
1. What the user is working on
2. File organization patterns
3. Potential automation opportunities"""
                
                try:
                    response = providers.ask_llm(prompt, max_output_tokens=500)
                    if response:
                        insights = [response]
                except Exception as e:
                    pass
            
            return {
                "success": True,
                "total_files": len(files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_types": file_types,
                "recent_files_count": len(recent_files),
                "insights": insights
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def auto_organize_drive(self) -> Dict[str, Any]:
        """Auto-organize Drive files into folders."""
        service = self.integration.get_service("drive")
        if not service:
            return {"success": False, "error": "Drive service not available"}
        
        try:
            # Get files in root
            results = service.files().list(
                q="'root' in parents and trashed=false",
                pageSize=100,
                fields="files(id,name,mimeType,createdTime)"
            ).execute()
            
            files = results.get("files", [])
            organized = 0
            
            # Create folders if needed
            folder_map = {
                "Documents": "application/vnd.google-apps.document",
                "Spreadsheets": "application/vnd.google-apps.spreadsheet",
                "Presentations": "application/vnd.google-apps.presentation",
                "PDFs": "application/pdf",
                "Images": "image/",
                "Archives": ["application/zip", "application/x-rar-compressed"]
            }
            
            folder_ids = {}
            
            for folder_name, mime_types in folder_map.items():
                # Check if folder exists
                folder_results = service.files().list(
                    q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and 'root' in parents",
                    fields="files(id,name)"
                ).execute()
                
                if folder_results.get("files"):
                    folder_ids[folder_name] = folder_results["files"][0]["id"]
                else:
                    # Create folder
                    folder = service.files().create(
                        body={
                            "name": folder_name,
                            "mimeType": "application/vnd.google-apps.folder",
                            "parents": ["root"]
                        },
                        fields="id"
                    ).execute()
                    folder_ids[folder_name] = folder["id"]
            
            # Move files to appropriate folders
            for file in files:
                file_mime = file["mimeType"]
                
                for folder_name, mime_types in folder_map.items():
                    if isinstance(mime_types, str):
                        if file_mime == mime_types or file_mime.startswith(mime_types):
                            # Move file
                            service.files().update(
                                fileId=file["id"],
                                addParents=[folder_ids[folder_name]],
                                removeParents=["root"],
                                fields="id, parents"
                            ).execute()
                            organized += 1
                            break
            
            return {
                "success": True,
                "files_processed": len(files),
                "files_organized": organized
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}


# Global manager instance
_manager: Optional[GoogleManager] = None


def get_google_manager() -> GoogleManager:
    """Get the global Google manager instance."""
    global _manager
    if not _manager:
        _manager = GoogleManager()
    return _manager
