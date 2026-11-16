"""Pull unread emails from Gmail and save them to the database.

Run it by hand with:  python -m app.ingest
"""

import re

from app import database, gmail

# Senders that are machines, not customers. We keep a record but never reply.
AUTOMATED_SENDER = re.compile(
    r"^(no[-_.]?reply|do[-_.]?not[-_.]?reply|mailer-daemon|postmaster|notifications?)@",
    re.IGNORECASE,
)


def is_automated(from_address: str) -> bool:
    """True if the email comes from an automated sender."""
    return bool(AUTOMATED_SENDER.match(from_address or ""))


def is_from_us(from_address: str) -> bool:
    """True if the email was sent by this inbox itself, for example a copy of
    our own reply. Answering those would have the agent writing to itself."""
    return (from_address or "").lower() == gmail.own_address()


def ingest_new_emails() -> dict:
    """Fetch unread emails and save the ones we have not seen before.

    Returns a count of what happened: saved, ignored, and already known.
    """
    counts = {"fetched": 0, "saved": 0, "ignored": 0, "already_known": 0}

    service = gmail.get_service()
    ids = gmail.list_email_ids(service)
    known = database.known_gmail_ids(ids)
    counts["fetched"] = len(ids)
    counts["already_known"] = len(known)

    # Only open the emails we have not saved before.
    for gmail_message_id in ids:
        if gmail_message_id in known:
            continue
        email = gmail.get_email(service, gmail_message_id)
        row = database.save_email(**email)

        if row is None:
            counts["already_known"] += 1
        elif is_from_us(email["from_address"]):
            database.set_email_status(row["id"], "ignored")
            counts["ignored"] += 1
            # A copy of our own reply: nobody needs to read it, so clear it.
            try:
                gmail.mark_read(gmail_message_id)
            except Exception:
                pass
        elif is_automated(email["from_address"]):
            database.set_email_status(row["id"], "ignored")
            counts["ignored"] += 1
        else:
            counts["saved"] += 1

    return counts


if __name__ == "__main__":
    result = ingest_new_emails()
    print(
        f"Fetched {result['fetched']} unread email(s): "
        f"{result['saved']} saved for a reply, "
        f"{result['ignored']} ignored as automated, "
        f"{result['already_known']} already in the database."
    )
