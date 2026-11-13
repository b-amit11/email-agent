"""The web backend. The review dashboard talks to this.

Start it with:  python -m uvicorn app.main:app --reload
"""

from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import database

app = FastAPI(title="Email Agent", version="0.1.0")


class ApproveRequest(BaseModel):
    """What the reviewer sends when approving. final_body is their edited text;
    leave it out to approve the AI's text unchanged."""

    final_body: str | None = None


def _get_pending_draft(draft_id: UUID) -> dict:
    """Find a draft and make sure it is still waiting for review."""
    draft = database.get_draft(str(draft_id))
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    if draft["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Draft was already reviewed (status: {draft['status']}).",
        )
    return draft


@app.get("/health")
def health() -> dict:
    """A simple check that the server is running."""
    return {"status": "ok"}


@app.get("/drafts")
def list_pending_drafts() -> list[dict]:
    """All drafts waiting for review, each with its original email."""
    return database.get_pending_drafts()


@app.post("/drafts/{draft_id}/approve")
def approve_draft(draft_id: UUID, request: ApproveRequest | None = None) -> dict:
    """Approve a draft, optionally with edited text. This does not send it."""
    _get_pending_draft(draft_id)
    final_body = request.final_body if request else None
    if final_body is not None and not final_body.strip():
        raise HTTPException(status_code=422, detail="The edited reply cannot be empty.")
    return database.review_draft(str(draft_id), approved=True, final_body=final_body)


@app.post("/drafts/{draft_id}/reject")
def reject_draft(draft_id: UUID) -> dict:
    """Reject a draft. It will never be sent."""
    _get_pending_draft(draft_id)
    return database.review_draft(str(draft_id), approved=False)
