# Email Agent

An AI assistant for a customer support inbox. It reads incoming emails from Gmail, drafts a reply using a set of company fact sheets, and puts each draft in front of a person. Nothing is sent to a customer until a person approves it.

## How it works

1. **Fetch.** Every 60 seconds the backend asks Gmail for unread emails and saves new ones to the database. Emails from automated senders (such as `no-reply@`) are saved but never answered.
2. **Draft.** For each new email, the agent writes a reply. It may only use facts from the files in `knowledge/`. If a question is not covered there, it says the team will follow up, and flags the draft as needing a follow-up.
3. **Review.** The dashboard shows each customer email beside its draft. A person can approve and send it, edit it first, or reject it.
4. **Send.** An approved reply is sent through Gmail in the same conversation as the customer's email. Each reply can be sent only once.

## What is in this repository

| Path | What it is |
|---|---|
| `app/main.py` | The web backend (FastAPI) and the background mail check |
| `app/gmail.py` | Gmail login, reading emails, sending replies |
| `app/agent.py` | The agent: its instructions and the model it uses |
| `app/knowledge.py` | Loads the fact sheets |
| `app/ingest.py`, `app/drafting.py`, `app/pipeline.py` | The fetch and draft steps |
| `app/database.py` | Every read and write to the database |
| `app/auth.py` | The dashboard login |
| `app/config.py` | Settings, read from `.env` |
| `knowledge/` | The fact sheets the agent answers from (sample data for a made-up shop) |
| `dashboard/` | The review page (React) |
| `db/` | SQL that creates the database tables |
| `evals/` | Test emails and the command that scores the agent's replies |
| `docs/` | Plain-language notes on how the project was built |

## Setup

You need Python 3.12, Node.js, a Supabase project, a Google Cloud project with the Gmail API enabled, and an Anthropic API key.

**1. Install the Python packages**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**2. Add your settings**

Copy `.env.example` to `.env` and fill in the three keys. For Supabase, use the secret key: the tables are locked so that only it can read or write them.

Also choose a `DASHBOARD_PASSWORD`. It is the password for the review page; until it is set, nobody can log in.

**3. Create the database tables**

In the Supabase SQL Editor, run the files in `db/` in order: `001_initial_tables.sql`, then `002_follow_up_flag.sql`.

**4. Connect Gmail**

In the Google Cloud console, create an OAuth client of type "Desktop app", download its file, and save it as `credentials/credentials.json`. Add the inbox's address as a test user on the OAuth consent screen. Then sign in once:

```powershell
python gmail_login.py
```

A browser opens for you to approve access. The login is saved to `credentials/token.json` and reused from then on.

**5. Install the dashboard packages**

```powershell
cd dashboard
npm install
```

## Running it

Start the backend from the project root:

```powershell
python -m uvicorn app.main:app --reload
```

In a second terminal, start the dashboard:

```powershell
cd dashboard
npm run dev
```

Open http://localhost:5173 and log in with your dashboard password. Send an email to the connected inbox; within a minute a draft appears on the page.

The backend also has a page listing everything it can do, at http://127.0.0.1:8000/docs.

## Changing what the agent knows

Edit or add `.md` files in `knowledge/`, then restart the backend. The fact sheets are read once at startup.

## Measuring reply quality

`evals/cases.json` holds test emails, each with a checklist of what a good reply must and must not say (`evals/cases.md` is the same content in readable form). To run them:

```powershell
python -m evals.run --dry-run        # free: tests the plumbing with fake models
python -m evals.run --variant v1     # real run: costs a small amount per email
```

The real run has the agent answer every test email, then a second model marks each reply against its checklist. Results are written to `evals/runs/reply-drafts/`.

