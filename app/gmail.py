"""Connecting to Gmail: logging in and getting a ready-to-use Gmail service."""

import base64
import html
import json
import re
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import get_settings

# What we ask Google to let us do: read, send, and label emails.
# This does not allow permanently deleting emails.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


# The login made from the GMAIL_TOKEN_JSON setting, kept so it is not rebuilt on every request.
_hosted_login: Credentials | None = None


def _hosted_credentials(token_json: str) -> Credentials:
    """Gmail login for a hosted server, where there is no token file and no browser.

    The whole content of token.json is supplied as the GMAIL_TOKEN_JSON setting.
    """
    global _hosted_login
    if _hosted_login and _hosted_login.valid:
        return _hosted_login

    creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    if not creds.valid:
        if not creds.refresh_token:
            raise RuntimeError(
                "GMAIL_TOKEN_JSON cannot be renewed. Run gmail_login.py on your own "
                "computer again and copy the new token.json into the setting."
            )
        creds.refresh(Request())
    _hosted_login = creds
    return creds


def get_credentials() -> Credentials:
    """Return a valid Gmail login.

    On your own computer: the first time, this opens a browser so you can sign
    in and approve. After that, the saved token file is reused and refreshed.

    On a hosted server: the login comes from the GMAIL_TOKEN_JSON setting.
    """
    settings = get_settings()
    if settings.gmail_token_json:
        return _hosted_credentials(settings.gmail_token_json)

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


def get_service():
    """Return a Gmail service object, used for every Gmail request.

    A fresh one is made each time, because one service object must not be
    used by two tasks at once (the background check and a send, for example).
    """
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


# ---------- sending emails ----------


def send_reply(
    to_address: str,
    subject: str | None,
    body: str,
    gmail_message_id: str,
    gmail_thread_id: str | None,
) -> dict:
    """Send a reply to an email, in the same conversation thread.

    Returns Gmail's record of the sent message.
    """
    service = get_service()

    # Look up the original email's own id header, so mail apps can link
    # our reply to it and show the two as one conversation.
    original = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=gmail_message_id,
            format="metadata",
            metadataHeaders=["Message-ID", "References"],
        )
        .execute()
    )
    headers = {h["name"].lower(): h["value"] for h in original["payload"].get("headers", [])}
    original_id = headers.get("message-id")

    subject = (subject or "").strip()
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}" if subject else "Re:"

    message = EmailMessage()
    message["To"] = to_address
    message["Subject"] = subject
    if original_id:
        message["In-Reply-To"] = original_id
        message["References"] = f"{headers.get('references', '')} {original_id}".strip()
    message.set_content(body)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    request_body = {"raw": raw}
    if gmail_thread_id:
        request_body["threadId"] = gmail_thread_id

    return service.users().messages().send(userId="me", body=request_body).execute()
