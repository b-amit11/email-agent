"""The whole website in one program: the dashboard page plus the backend.

This is what runs in Docker and on a hosted server:

    python -m uvicorn app.site:site

Everything under /api goes to the backend. Everything else is the dashboard
page, taken from the built files in dashboard/dist.

While developing you can still run the two halves separately:
`uvicorn app.main:app --reload` for the backend and `npm run dev` for the page.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.main import app as backend
from app.main import lifespan

DASHBOARD_FILES = Path(__file__).resolve().parent.parent / "dashboard" / "dist"

# The background mail check is started here, because a program mounted
# inside another one does not run its own start-up steps.
site = FastAPI(title="Email Agent", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

# The backend's own help pages are handy while developing, but a visitor to
# the public website has no use for them, so they are taken out here.
HELP_PAGES = {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}
backend.router.routes = [
    route for route in backend.router.routes if getattr(route, "path", None) not in HELP_PAGES
]
site.mount("/api", backend)

if DASHBOARD_FILES.is_dir():
    site.mount("/", StaticFiles(directory=DASHBOARD_FILES, html=True), name="dashboard")
