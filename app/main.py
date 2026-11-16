"""The web backend. The review dashboard talks to this.

Start it with:  python -m uvicorn app.main:app --reload
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from app import auth, database, gmail, pipeline
from app.config import get_settings

log = logging.getLogger("uvicorn.error")


async def _check_mail_forever(interval: int) -> None:
    """Every `interval` seconds: fetch new emails and draft replies."""
    while True:
        try:
            result = await asyncio.to_thread(pipeline.run_once)
            if result.get("saved") or result.get("ignored") or result.get("drafted"):
                log.info(
                    "Mail check: %s new, %s ignored, %s drafted.",
                    result.get("saved", 0),
                    result.get("ignored", 0),
                    result.get("drafted", 0),
                )
        except Exception:
            # One bad round must not stop the checking; try again next time.
            log.exception("Mail check failed; will try again.")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the background mail check when the server starts; stop it at shutdown."""
    interval = get_settings().poll_interval_seconds
    task = None
    if interval > 0:
        log.info("Checking Gmail every %s seconds.", interval)
        task = asyncio.create_task(_check_mail_forever(interval))
    else:
        log.info("Automatic Gmail checking is off.")
    yield
    if task:
        task.cancel()


app = FastAPI(title="Email Agent", version="0.1.0", lifespan=lifespan)


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


class LoginRequest(BaseModel):
    password: str


@app.post("/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict:
    """Check the password and hand the browser a pass, kept in a cookie."""
    client_address = request.client.host if request.client else "unknown"
    auth.check_password(body.password, client_address)
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.make_token(),
        max_age=auth.SESSION_SECONDS,
        httponly=True,  # page scripts cannot read it
        samesite="strict",  # other websites cannot use it
        secure=get_settings().cookie_secure,
    )
    return {"logged_in": True}


@app.post("/logout")
def logout(response: Response) -> dict:
    """Throw the pass away."""
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"logged_in": False}


@app.get("/session")
def session(request: Request) -> dict:
    """Lets the dashboard ask: am I logged in?"""
    return {"logged_in": auth.token_is_valid(request.cookies.get(auth.SESSION_COOKIE))}


@app.post("/check-mail", dependencies=[Depends(auth.require_login)])
def check_mail_now() -> dict:
    """Fetch new emails and draft replies right now, without waiting."""
    try:
        return pipeline.run_once()
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Mail check failed: {error}") from error


@app.get("/drafts", dependencies=[Depends(auth.require_login)])
def list_open_drafts() -> list[dict]:
    """Drafts that still need a person: waiting for review, or approved but
    not sent yet. Each comes with its original email."""
    return database.get_open_drafts()


@app.get("/summary", dependencies=[Depends(auth.require_login)])
def summary() -> dict:
    """How many emails were received, and what became of their drafts."""
    return database.get_counts()


@app.get("/history", dependencies=[Depends(auth.require_login)])
def list_filed_drafts() -> list[dict]:
    """The filing cabinet: drafts that were sent or rejected, newest first.
    Each comes with its original email."""
    return database.get_filed_drafts()


@app.post("/drafts/{draft_id}/approve", dependencies=[Depends(auth.require_login)])
def approve_draft(draft_id: UUID, request: ApproveRequest | None = None) -> dict:
    """Approve a draft, optionally with edited text. This does not send it."""
    _get_pending_draft(draft_id)
    final_body = request.final_body if request else None
    if final_body is not None and not final_body.strip():
        raise HTTPException(status_code=422, detail="The edited reply cannot be empty.")
    return database.review_draft(str(draft_id), approved=True, final_body=final_body)


@app.post("/drafts/{draft_id}/reject", dependencies=[Depends(auth.require_login)])
def reject_draft(draft_id: UUID) -> dict:
    """Reject a draft. It will never be sent."""
    _get_pending_draft(draft_id)
    return database.review_draft(str(draft_id), approved=False)


@app.post("/drafts/{draft_id}/send", dependencies=[Depends(auth.require_login)])
def send_draft(draft_id: UUID) -> dict:
    """Send an approved draft to the customer, as a reply in the same thread.

    Only approved drafts can be sent, and each one only once.
    """
    draft = database.get_draft(str(draft_id))
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found.")

    claimed = database.claim_draft_for_sending(str(draft_id))
    if claimed is None:
        raise HTTPException(
            status_code=409,
            detail=f"Only approved drafts can be sent (status: {draft['status']}).",
        )

    try:
        email = database.get_email(claimed["email_id"])
        gmail.send_reply(
            to_address=email["from_address"],
            subject=email["subject"],
            body=claimed["final_body"],
            gmail_message_id=email["gmail_message_id"],
            gmail_thread_id=email["gmail_thread_id"],
        )
    except Exception as error:
        database.release_draft_claim(str(draft_id))
        raise HTTPException(
            status_code=502,
            detail=f"Sending failed, the draft is still approved: {error}",
        ) from error

    database.set_email_status(claimed["email_id"], "sent")
    return claimed
