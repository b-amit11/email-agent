"""All reading and writing to the database goes through this file."""

from datetime import datetime, timezone
from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_client() -> Client:
    """Connect to Supabase once and reuse the connection."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- emails ----------


def save_email(
    gmail_message_id: str,
    from_address: str,
    subject: str | None = None,
    body: str | None = None,
    from_name: str | None = None,
    gmail_thread_id: str | None = None,
    received_at: str | None = None,
) -> dict | None:
    """Save an incoming email.

    Returns the saved row, or None if this email was already saved before.
    """
    result = (
        get_client()
        .table("emails")
        .upsert(
            {
                "gmail_message_id": gmail_message_id,
                "gmail_thread_id": gmail_thread_id,
                "from_address": from_address,
                "from_name": from_name,
                "subject": subject,
                "body": body,
                "received_at": received_at,
            },
            on_conflict="gmail_message_id",
            ignore_duplicates=True,
        )
        .execute()
    )
    return result.data[0] if result.data else None


def get_emails(status: str = "new") -> list[dict]:
    """List emails with the given status, oldest first."""
    result = (
        get_client()
        .table("emails")
        .select("*")
        .eq("status", status)
        .order("received_at")
        .execute()
    )
    return result.data


def set_email_status(email_id: str, status: str) -> None:
    """Change an email's status: new, drafted, sent, or ignored."""
    get_client().table("emails").update({"status": status}).eq("id", email_id).execute()


# ---------- drafts ----------


def save_draft(email_id: str, body: str, model: str | None = None) -> dict:
    """Save an AI-written reply and mark its email as drafted."""
    result = (
        get_client()
        .table("drafts")
        .insert({"email_id": email_id, "body": body, "model": model})
        .execute()
    )
    set_email_status(email_id, "drafted")
    return result.data[0]


def get_pending_drafts() -> list[dict]:
    """List drafts waiting for review, each with its original email attached."""
    result = (
        get_client()
        .table("drafts")
        .select("*, email:emails(*)")
        .eq("status", "pending")
        .order("created_at")
        .execute()
    )
    return result.data


def review_draft(draft_id: str, approved: bool, final_body: str | None = None) -> dict:
    """Record the reviewer's decision.

    If approved, final_body is the text to send; it defaults to the AI's text.
    """
    client = get_client()
    changes: dict = {
        "status": "approved" if approved else "rejected",
        "reviewed_at": _now(),
    }
    if approved:
        if final_body is None:
            current = client.table("drafts").select("body").eq("id", draft_id).execute()
            final_body = current.data[0]["body"]
        changes["final_body"] = final_body

    result = client.table("drafts").update(changes).eq("id", draft_id).execute()
    return result.data[0]


def mark_draft_sent(draft_id: str) -> dict:
    """Mark a draft as sent, and its email too."""
    result = (
        get_client()
        .table("drafts")
        .update({"status": "sent", "sent_at": _now()})
        .eq("id", draft_id)
        .execute()
    )
    draft = result.data[0]
    set_email_status(draft["email_id"], "sent")
    return draft
