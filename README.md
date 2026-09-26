# OpenShelf

OTT search that actually listens.

Type a scene you half-remember. Or a messy filter dump. You get ranked titles from *your* catalog, plus a straight answer for why each one showed up.

## Forgot the name?

No title. No actor. Just the bit stuck in your head.

> "a guy fakes being blind and it turns out he witnessed a murder"
> → **Andhadhun**, 98%, one sentence why.

Nothing in the catalog? We say so. We don't invent a winner.

## Search like a human

> "90-120 min thriller, non-English, after 2018, IMDb > 7, no horror"
> "mohanlal movies" · "movies with a double role" · "triller under 5 imdb"

Typos, actor names, dual roles, weird rating phrasing. Rules first. AI as backup. 

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

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to FastAPI.

## AI key (optional)

Copy `backend/.env.example` to `backend/.env` and set `OPENAI_API_KEY`. Default is Gemini (free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)). Point `OPENAI_BASE_URL` / `OPENAI_MODEL` at OpenAI or any other compatible provider.

No key? Filter search still works. Scene recall falls back to a labeled best-effort guess.

## Tests

```bash
cd backend && PYTHONPATH=. pytest -q
```
