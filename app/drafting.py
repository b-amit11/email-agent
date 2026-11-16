"""Write a draft reply for every new email and save it for human review.

Run it by hand with:  python -m app.drafting
"""

import logging

from app import database
from app.agent import write_draft
from app.config import get_settings

log = logging.getLogger("uvicorn.error")


def draft_new_emails() -> list[dict]:
    """Draft a reply for each email with status 'new'. Nothing is sent.

    Returns the saved drafts.
    """
    model_name = get_settings().ai_model
    drafts = []
    for email in database.get_emails("new"):
        # Claim the email first. If another worker (a second server, or a
        # command run by hand) already took it, skip it: one email, one draft.
        if database.claim_email_for_drafting(email["id"]) is None:
            continue
        try:
            draft = write_draft(email)
            drafts.append(
                database.save_draft(
                    email["id"],
                    draft.reply,
                    model=model_name,
                    needs_follow_up=draft.needs_follow_up,
                    follow_up_note=draft.follow_up_note,
                    sources=draft.sources,
                )
            )
        except Exception:
            # Put it back so the next round tries again, and carry on.
            database.set_email_status(email["id"], "new")
            log.exception("Could not draft a reply for email %s.", email["id"])
    return drafts


if __name__ == "__main__":
    saved = draft_new_emails()
    print(f"Wrote {len(saved)} draft(s). They are waiting for review.")
