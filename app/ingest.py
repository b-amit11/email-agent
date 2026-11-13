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


def ingest_new_emails() -> dict:
    """Fetch unread emails and save the ones we have not seen before.

    Returns a count of what happened: saved, ignored, and already known.
    """
    counts = {"fetched": 0, "saved": 0, "ignored": 0, "already_known": 0}

    for email in gmail.fetch_emails():
        counts["fetched"] += 1
        row = database.save_email(**email)

        if row is None:
            counts["already_known"] += 1
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
