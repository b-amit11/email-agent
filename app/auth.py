"""Login for the review dashboard.

There is one shared password, set as DASHBOARD_PASSWORD in .env. A correct
password earns a signed pass, kept in a browser cookie, that is good for a
week. Every request that reads or sends email must carry a valid pass.
"""

import hashlib
import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import get_settings

SESSION_COOKIE = "reply_desk_session"
SESSION_SECONDS = 7 * 24 * 60 * 60

# Slow down password guessing: at most 5 wrong tries per address in 5 minutes.
MAX_WRONG_TRIES = 5
TRY_WINDOW_SECONDS = 5 * 60
_wrong_tries: dict[str, deque] = defaultdict(deque)


def password_is_set() -> bool:
    return bool(get_settings().dashboard_password)


def _signing_key() -> bytes:
    """The key used to sign passes. Changing the password cancels every old pass."""
    return hashlib.sha256(("session:" + get_settings().dashboard_password).encode()).digest()


def _sign(expires: str) -> str:
    return hmac.new(_signing_key(), expires.encode(), hashlib.sha256).hexdigest()


def make_token() -> str:
    """Create a pass: an expiry time plus a signature only this server can make."""
    expires = str(int(time.time()) + SESSION_SECONDS)
    return f"{expires}.{_sign(expires)}"


def token_is_valid(token: str | None) -> bool:
    """A pass is valid if its signature is ours and it has not expired."""
    if not token or not password_is_set():
        return False
    expires, _, signature = token.partition(".")
    if not expires.isdigit() or not hmac.compare_digest(signature, _sign(expires)):
        return False
    return int(expires) > time.time()


def check_password(candidate: str, client_address: str) -> None:
    """Raise an error unless the password is right. Counts wrong tries."""
    if not password_is_set():
        raise HTTPException(
            status_code=503,
            detail="No dashboard password is set. Add DASHBOARD_PASSWORD to .env and restart the backend.",
        )

    now = time.time()
    tries = _wrong_tries[client_address]
    while tries and now - tries[0] > TRY_WINDOW_SECONDS:
        tries.popleft()
    if len(tries) >= MAX_WRONG_TRIES:
        raise HTTPException(status_code=429, detail="Too many wrong tries. Wait a few minutes.")

    if not hmac.compare_digest(candidate.encode(), get_settings().dashboard_password.encode()):
        tries.append(now)
        raise HTTPException(status_code=401, detail="Wrong password.")
    tries.clear()


def require_login(request: Request) -> None:
    """Used by every protected page: refuse the request without a valid pass."""
    if not token_is_valid(request.cookies.get(SESSION_COOKIE)):
        raise HTTPException(status_code=401, detail="Please log in.")
