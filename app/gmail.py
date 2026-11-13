"""Connecting to Gmail: logging in and getting a ready-to-use Gmail service."""

import base64
import html
import re
from datetime import datetime, timezone
from email.utils import parseaddr
from functools import lru_cache
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import get_settings

# What we ask Google to let us do: read, send, and label emails.
# This does not allow permanently deleting emails.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def get_credentials() -> Credentials:
    """Return a valid Gmail login.

    The first time, this opens a browser so you can sign in and approve.
    After that, the saved token file is reused and refreshed automatically.
    """
    settings = get_settings()
    credentials_path = Path(settings.gmail_credentials_path)
    token_path = Path(settings.gmail_token_path)

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not credentials_path.exists():
            raise FileNotFoundError(
                f"Gmail credentials file not found at {credentials_path}. "
                "Download it from the Google Cloud console and put it there."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
        creds = flow.run_local_server(port=0)

    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


@lru_cache
def get_service():
    """Return a Gmail service object, used for every Gmail request."""
    return build("gmail", "v1", credentials=get_credentials(), cache_discovery=False)


# ---------- reading emails ----------


def _decode(data: str) -> str:
    """Gmail sends text in a web-safe encoding; turn it back into normal text."""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _find_part(payload: dict, mime_type: str) -> str | None:
    """Search an email (and the parts nested inside it) for text of one kind."""
    is_attachment = bool(payload.get("filename"))
    data = payload.get("body", {}).get("data")
    if payload.get("mimeType") == mime_type and data and not is_attachment:
        return _decode(data)
    for part in payload.get("parts", []):
        found = _find_part(part, mime_type)
        if found:
            return found
    return None


def _html_to_text(source: str) -> str:
    """Rough conversion of an HTML email into plain text."""
    source = re.sub(r"(?is)<(script|style|head).*?</\1>", " ", source)
    source = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", source)
    source = re.sub(r"<[^>]+>", " ", source)
    source = html.unescape(source)
    source = re.sub(r"[ \t\xa0]+", " ", source)
    return re.sub(r"\n\s*\n+", "\n\n", source).strip()


def _extract_body(payload: dict) -> str:
    """Get the readable text of an email, preferring the plain-text version."""
    text = _find_part(payload, "text/plain")
    if text and text.strip():
        return text.strip()
    html_source = _find_part(payload, "text/html")
    return _html_to_text(html_source) if html_source else ""


def _parse_message(message: dict) -> dict:
    """Turn Gmail's raw message into the simple fields our database stores."""
    payload = message.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
    from_name, from_address = parseaddr(headers.get("from", ""))
    received = datetime.fromtimestamp(int(message["internalDate"]) / 1000, tz=timezone.utc)
    return {
        "gmail_message_id": message["id"],
        "gmail_thread_id": message.get("threadId"),
        "from_address": from_address,
        "from_name": from_name or None,
        "subject": headers.get("subject"),
        "body": _extract_body(payload),
        "received_at": received.isoformat(),
    }


def fetch_emails(query: str = "is:unread in:inbox", max_results: int = 10) -> list[dict]:
    """Fetch emails matching a Gmail search. By default: unread ones in the inbox.

    This only reads. It does not mark anything as read or change the mailbox.
    """
    service = get_service()
    listing = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    emails = []
    for item in listing.get("messages", []):
        message = (
            service.users()
            .messages()
            .get(userId="me", id=item["id"], format="full")
            .execute()
        )
        emails.append(_parse_message(message))
    return emails
