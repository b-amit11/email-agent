"""Write a draft reply for every new email and save it for human review.

Run it by hand with:  python -m app.drafting
"""

from app import database
from app.agent import write_reply
from app.config import get_settings


def draft_new_emails() -> list[dict]:
    """Draft a reply for each email with status 'new'. Nothing is sent.

    Returns the saved drafts.
    """
    model_name = get_settings().ai_model
    drafts = []
    for email in database.get_emails("new"):
        reply = write_reply(email)
        drafts.append(database.save_draft(email["id"], reply, model=model_name))
    return drafts


if __name__ == "__main__":
    saved = draft_new_emails()
    print(f"Wrote {len(saved)} draft(s). They are waiting for review.")
