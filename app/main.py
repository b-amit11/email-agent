"""The web backend. The review dashboard talks to this.

Start it with:  python -m uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app import database

app = FastAPI(title="Email Agent", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """A simple check that the server is running."""
    return {"status": "ok"}


@app.get("/drafts")
def list_pending_drafts() -> list[dict]:
    """All drafts waiting for review, each with its original email."""
    return database.get_pending_drafts()
