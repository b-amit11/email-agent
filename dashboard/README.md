# Review dashboard

The web page where a person reviews the AI-written reply drafts.

## Run it

The Python backend must be running first (from the project root):

```
python -m uvicorn app.main:app --reload
```

Then, in a second terminal:

```
cd dashboard
npm install
npm run dev
```

Open http://localhost:5173.
