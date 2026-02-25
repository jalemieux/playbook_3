import base64
import logging
import time
from email.mime.text import MIMEText
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.orchestrator import handler

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _get_gmail_service(credentials_path: str):
    """Authenticate and return Gmail API service."""
    token_path = Path(credentials_path).parent / "token.json"
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _get_unread_messages(service):
    """Fetch unread messages from inbox."""
    result = service.users().messages().list(
        userId="me", q="is:unread", maxResults=5
    ).execute()
    return result.get("messages", [])


def _get_message_text(service, msg_id: str) -> tuple[str, str]:
    """Get message body text and sender. Returns (text, sender)."""
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    sender = headers.get("From", "")

    # Extract plain text body
    parts = msg["payload"].get("parts", [])
    if parts:
        for part in parts:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                return base64.urlsafe_b64decode(data).decode(), sender
    # Fallback: try body directly
    data = msg["payload"].get("body", {}).get("data", "")
    if data:
        return base64.urlsafe_b64decode(data).decode(), sender
    return msg.get("snippet", ""), sender


def _send_reply(service, to: str, subject: str, body: str):
    """Send an email reply."""
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = f"Re: {subject}"
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def _mark_as_read(service, msg_id: str):
    """Mark a message as read."""
    service.users().messages().modify(
        userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()


def start_gmail(config: dict, poll_interval: int = 60) -> None:
    """Poll Gmail for unread messages and process them."""
    service = _get_gmail_service(config["gmail_credentials_path"])
    logger.info("Gmail polling started (every %ds)", poll_interval)

    while True:
        try:
            messages = _get_unread_messages(service)
            for msg_meta in messages:
                msg_id = msg_meta["id"]
                text, sender = _get_message_text(service, msg_id)
                logger.info("Processing email from %s", sender)

                def reply_fn(response, _sender=sender):
                    _send_reply(service, _sender, "Agent Reply", response)

                handler(text, reply_fn, config, session_id=msg_id)
                _mark_as_read(service, msg_id)
        except Exception:
            logger.exception("Gmail polling error")

        time.sleep(poll_interval)
