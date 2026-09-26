# OpenShelf

Your own OTT search engine — not another recommendation feed. Describe what you want, get a filtered, ranked, **explained** catalog.

## 🧠 Forgot the name?

The main event. Half-remember a scene, a twist, a vibe — no title, no actor — and it matches against what the AI actually knows about each film's plot, not just a one-line blurb.

> "a guy fakes being blind and it turns out he witnessed a murder"
> → **Andhadhun**, 98% confidence, one honest sentence why.

No match in the catalog? It says so — never a fake guess.

## Also just... search

> "90–120 min thriller, non-English, after 2018, IMDb > 7, no horror"
> "mohanlal movies" · "movies with a double role" · "triller under 5 imdb"

Typos, messy ratings, actor names, dual-role plots — rules first, AI as backup, catalog always has the final word.

## Run it

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --reload --port 8001
```

```bash
cd frontend
npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173) — Vite proxies `/api` to FastAPI.

## AI key (optional)

Copy `backend/.env.example` → `backend/.env` and set `OPENAI_API_KEY`. Defaults to Google's Gemini (free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)); point `OPENAI_BASE_URL`/`OPENAI_MODEL` at OpenAI or any other OpenAI-compatible provider instead. No key → search still works via rules + embeddings, and scene recall falls back to a labeled best-effort guess instead of true plot recall.

## Tests

```bash
cd backend && PYTHONPATH=. pytest -q
```
