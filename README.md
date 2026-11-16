# Email Agent

An AI assistant for a customer support inbox. It reads incoming emails from Gmail, drafts a reply using a set of company fact sheets, and puts each draft in front of a person. Nothing is sent to a customer until a person approves it.

## How it works

1. **Fetch.** Every 60 seconds the backend asks Gmail for unread emails and saves new ones to the database. Emails from automated senders (such as `no-reply@`) are saved but never answered.
2. **Draft.** For each new email, the agent writes a reply. It may only use facts from the files in `knowledge/`. If a question is not covered there, it says the team will follow up, and flags the draft as needing a follow-up.
3. **Review.** The dashboard shows each customer email beside its draft. A person can approve and send it, edit it first, or reject it.
4. **Send.** An approved reply is sent through Gmail in the same conversation as the customer's email. Each reply can be sent only once.
5. **File.** Every reply that was sent or rejected is kept, and the dashboard's filing cabinet lists them all.

## What the reviewer can do

- **Approve, edit, or reject** each draft. Sending always asks for a second click.
- **Ask for a rewrite.** Type what should change ("shorter", "apologise for the delay") and the agent writes the draft again. It still may only use the fact sheets.
- **See where an answer came from.** Each draft names the fact sheets it used; clicking a name opens that sheet.
- **Read the fact sheets** the agent answers from, on their own page.
- **Look back.** The filing cabinet lists every reply that was sent or rejected. It can be searched, filtered (including replies that still owe a follow-up), and downloaded as a spreadsheet file.
- **Keep the inbox tidy.** An email is marked as read in Gmail once its reply is sent.

## What is in this repository

| Path | What it is |
|---|---|
| `app/main.py` | The web backend (FastAPI) and the background mail check |
| `app/site.py` | Backend and dashboard together as one website, for Docker and hosting |
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

In the Supabase SQL Editor, run the files in `db/` in order: `001_initial_tables.sql`, `002_follow_up_flag.sql`, then `003_sources.sql`.

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

## Running it with Docker

With Docker Desktop installed, the whole project starts with one command from the project root:

```powershell
docker compose up --build
```

Then open http://localhost:8080. Press Ctrl+C to stop.

Do the Gmail sign-in from the Setup section first, so that `credentials/token.json` exists. The container reads your secrets from `.env` when it starts; nothing secret is stored inside the image.

One image holds everything: the dashboard is built into plain web files, and the Python program serves them alongside the backend (`app/site.py`).

## Hosting it online

The same image runs on any service that can build a Dockerfile. `render.yaml` describes a free web service on [Render](https://render.com):

1. In Render, choose **New > Blueprint** and pick this repository.
2. When asked, fill in the secrets: `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, and `DASHBOARD_PASSWORD`, with the same values as your `.env`.
3. For `GMAIL_TOKEN_JSON`, paste the whole content of `credentials/token.json`. A hosted server has no browser to sign in with, so it uses the login you made on your own computer.

Render's free plan puts the service to sleep after 15 minutes without a visitor, and it takes about a minute to wake. Emails are only checked while it is awake; keeping the dashboard open keeps it awake.

## Changing what the agent knows

Edit or add `.md` files in `knowledge/`, then restart the backend. The fact sheets are read once at startup.

## Measuring reply quality

`evals/cases.json` holds test emails, each with a checklist of what a good reply must and must not say (`evals/cases.md` is the same content in readable form). To run them:

```powershell
python -m evals.run --dry-run        # free: tests the plumbing with fake models
python -m evals.run --variant v1     # real run: costs a small amount per email
```

The real run has the agent answer every test email, then a second model marks each reply against its checklist. Results are written to `evals/runs/reply-drafts/`.

To see the test emails go through the real program instead, place them in the connected inbox:

```powershell
python -m evals.fill_inbox
```

Each one arrives as an unread email, gets a draft, and appears on the dashboard for review. The made-up customers use addresses that lead back to the same inbox, so approved replies never reach a stranger.

