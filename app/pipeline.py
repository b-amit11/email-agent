"""One full round of work: fetch new emails, then draft replies for them.

Run it by hand with:  python -m app.pipeline
"""

import threading

from app.drafting import draft_new_emails
from app.ingest import ingest_new_emails

# Only one round may run at a time. Two rounds at once could both pick up
# the same new email and write two drafts for it.
_running = threading.Lock()


def run_once() -> dict:
    """Do one round. Returns counts of what happened.

    If a round is already running, this does nothing and says so.
    """
    if not _running.acquire(blocking=False):
        return {"skipped": True}
    try:
        counts = ingest_new_emails()
        drafts = draft_new_emails()
        return {"skipped": False, **counts, "drafted": len(drafts)}
    finally:
        _running.release()


if __name__ == "__main__":
    print(run_once())
