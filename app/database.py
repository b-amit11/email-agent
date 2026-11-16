"""All reading and writing to the database goes through this file."""

from datetime import datetime, timedelta, timezone
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


def known_gmail_ids(gmail_message_ids: list[str]) -> set[str]:
    """Of the given Gmail message ids, return the ones already saved."""
    if not gmail_message_ids:
        return set()
    result = (
        get_client()
        .table("emails")
        .select("gmail_message_id")
        .in_("gmail_message_id", gmail_message_ids)
        .execute()
    )
    return {row["gmail_message_id"] for row in result.data}


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


def claim_email_for_drafting(email_id: str) -> dict | None:
    """Flip a 'new' email to 'drafted' so that only one worker writes its reply.

    Returns the email if we got the claim, or None if someone else already
    took it. Call this BEFORE asking the AI. If drafting then fails, set the
    status back to 'new' so it is tried again.
    """
    result = (
        get_client()
        .table("emails")
        .update({"status": "drafted"})
        .eq("id", email_id)
        .eq("status", "new")
        .execute()
    )
    return result.data[0] if result.data else None


def release_stuck_emails(older_than_minutes: int = 30) -> int:
    """Put emails back to 'new' if they were claimed for drafting but no draft
    was ever saved, which happens when the program is stopped mid-draft.

    Only emails saved more than `older_than_minutes` ago are touched, so a
    draft that is being written right now is left alone. Returns how many
    emails were released.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)).isoformat()
    stuck = (
        get_client()
        .table("emails")
        .select("id, drafts(id)")
        .eq("status", "drafted")
        .lt("created_at", cutoff)
        .is_("drafts", "null")
        .execute()
    )
    for row in stuck.data:
        set_email_status(row["id"], "new")
    return len(stuck.data)


# ---------- drafts ----------


def save_draft(
    email_id: str,
    body: str,
    model: str | None = None,
    needs_follow_up: bool = False,
    follow_up_note: str | None = None,
) -> dict:
    """Save an AI-written reply and mark its email as drafted."""
    result = (
        get_client()
        .table("drafts")
        .insert(
            {
                "email_id": email_id,
                "body": body,
                "model": model,
                "needs_follow_up": needs_follow_up,
                "follow_up_note": follow_up_note,
            }
        )
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


def get_open_drafts() -> list[dict]:
    """List drafts that still need a person: waiting for review, or approved
    but not sent yet. Each comes with its original email attached."""
    result = (
        get_client()
        .table("drafts")
        .select("*, email:emails(*)")
        .in_("status", ["pending", "approved"])
        .order("created_at")
        .execute()
    )
    return result.data


def get_filed_drafts(limit: int = 200) -> list[dict]:
    """List drafts a person has finished with: sent or rejected, newest first.
    Each comes with its original email attached."""
    result = (
        get_client()
        .table("drafts")
        .select("*, email:emails(*)")
        .in_("status", ["sent", "rejected"])
        .order("reviewed_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


def _count(table: str, statuses: list[str] | None = None) -> int:
    """Count the rows in a table, optionally only those with certain statuses."""
    query = get_client().table(table).select("id", count="exact")
    if statuses:
        query = query.in_("status", statuses)
    return query.limit(1).execute().count or 0


def get_counts() -> dict:
    """The numbers for the top of the dashboard."""
    # Emails that were never meant to be answered (automated senders, copies
    # of our own replies) are left out of "received".
    return {
        "received": _count("emails", ["new", "drafted", "sent"]),
        "waiting": _count("drafts", ["pending", "approved"]),
        "sent": _count("drafts", ["sent"]),
        "rejected": _count("drafts", ["rejected"]),
    }


def get_draft(draft_id: str) -> dict | None:
    """Get one draft by its id, or None if there is no such draft."""
    result = get_client().table("drafts").select("*").eq("id", draft_id).execute()
    return result.data[0] if result.data else None


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


def claim_draft_for_sending(draft_id: str) -> dict | None:
    """Flip an approved draft to 'sent' so that it can only ever be sent once.

    Returns the draft if we got the claim, or None if it was not in the
    'approved' state (not reviewed yet, rejected, or already sent).
    Call this BEFORE sending. If sending then fails, call release_draft_claim.
    """
    result = (
        get_client()
        .table("drafts")
        .update({"status": "sent", "sent_at": _now()})
        .eq("id", draft_id)
        .eq("status", "approved")
        .execute()
    )
    return result.data[0] if result.data else None


def release_draft_claim(draft_id: str) -> None:
    """Sending failed: put the draft back to 'approved' so it can be retried."""
    (
        get_client()
        .table("drafts")
        .update({"status": "approved", "sent_at": None})
        .eq("id", draft_id)
        .execute()
    )


def get_email(email_id: str) -> dict | None:
    """Get one email by its id, or None if there is no such email."""
    result = get_client().table("emails").select("*").eq("id", email_id).execute()
    return result.data[0] if result.data else None
