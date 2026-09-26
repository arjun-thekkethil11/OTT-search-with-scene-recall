"""Tiny LLM intent layer: interpret messy search text, then Python filters the catalog.

The model never sees full overviews. Parse call = user query + a short digest
(genres / languages / people names). Optional refine call = a TSV of already
filtered hits. That's a few hundred tokens per search, not the whole shelf.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from app.models import ParsedQuery, SearchHit, Title

if TYPE_CHECKING:
    from app.search import SemanticIndex

_ENV_LOADED = False


def _load_dotenv() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    for path in (
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def ai_enabled() -> bool:
    _load_dotenv()
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL"))


def interpret_query(query: str, titles: list[Title]) -> dict:
    """Return overlay fields for ParsedQuery, or {} if the model is unused/fails."""
    if not ai_enabled() or not (query or "").strip():
        return {}
    digest = _digest(titles)
    system = (
        "You turn a messy OTT search query into JSON filters for a fixed catalog. "
        "Do not invent titles. Fix typos (triller=Thriller, mammooty=Mammootty). "
        "If the user contradicts themselves ('more than below 5'), use the bound they "
        "clearly meant (below 5 → imdb_max 5). "
        "Set dual_role true for double/dual role, two characters, two roles — not stunt double. "
        "people_include values must be copied from PEOPLE when a person is asked for. "
        "If dual_role is true, only people in DUAL_ROLE can actually match. "
        "genres must be copied from GENRES. "
        "Output JSON only with any of: "
        "runtime_min, runtime_max, year_min, year_max, imdb_min, imdb_max, "
        "genres_include, genres_exclude, languages_include, languages_exclude, "
        "non_english, countries_include, types, platforms_include, people_include, dual_role, semantic_text. "
        "types is [\"movie\"] and/or [\"series\"]. Unused keys omitted. Numbers or null."
    )
    user = f"DIGEST\n{digest}\n\nQUERY\n{query.strip()}"
    data = _chat(system, user, max_tokens=280)
    return _as_overlay(data)


def refine_hits(query: str, hits: list[SearchHit], limit: int) -> list[SearchHit] | None:
    """Drop/reorder compact hits that do not actually satisfy the query. None = keep as-is."""
    if not ai_enabled() or len(hits) < 2:
        return None
    rows = []
    for hit in hits[:24]:
        t = hit.title
        rows.append(
            f"{t.id}|{t.title}|{t.year}|{t.type}|imdb={t.imdb}|{','.join(t.genres[:4])}|{','.join(t.languages[:2])}|dual={','.join(t.dual_role_cast[:3])}"
        )
    system = (
        "You filter catalog rows. Return JSON {\"ids\": [\"id\", ...]} in best-first order. "
        "Keep only rows that satisfy the user query. Drop rating/genre/type mismatches. "
        "If they asked for a double/dual role, keep only rows whose dual= field lists that actor. "
        "Do not add ids that are not listed. If none fit, ids is []."
    )
    user = f"QUERY\n{query.strip()}\n\nROWS\n" + "\n".join(rows)
    data = _chat(system, user, max_tokens=220)
    if not isinstance(data, dict):
        return None
    wanted = data.get("ids")
    if not isinstance(wanted, list):
        return None
    by_id = {h.title.id: h for h in hits}
    ordered = [by_id[i] for i in wanted if isinstance(i, str) and i in by_id]
    if not ordered:
        return None
    return ordered[:limit]


def recall_scene(
    query: str, titles: list[Title], index: "SemanticIndex", limit: int = 6
) -> tuple[list[dict], bool]:
    """"I forgot the name but I remember this scene" search.

    Unlike interpret_query/refine_hits (which only ever see short digests), this call
    sends the model a compact one-line-per-title catalog and explicitly tells it to use
    its OWN real-world knowledge of each specific film/show — twists, iconic scenes,
    dialogue — not just the short hint string, to judge whether a vague memory matches.
    It is only invoked when the user opens this dedicated "remember a scene" flow, not on
    every keystroke of normal search, so the extra token spend stays a rare, deliberate cost.

    Returns (hits, ai_used). hits are dicts of {id, confidence, why}, ids are always
    verified against the catalog (no hallucinated titles ever reach the caller). If the
    AI call itself fails or is unavailable, falls back to embedding/TF-IDF similarity
    with an honest, capped confidence and ai_used=False so the UI can say so.
    """
    query = (query or "").strip()
    if not query:
        return [], False

    def _fallback() -> list[dict]:
        scores = index.scores(query)
        ranked = sorted(zip(titles, scores), key=lambda pair: -pair[1])
        return [
            {
                "id": t.id,
                "confidence": int(round(min(max(score, 0.0), 1.0) * 60)),
                "why": "Closest wording/theme match we could find — no AI plot recall available.",
            }
            for t, score in ranked[:limit]
            if score > 0.05
        ]

    if not ai_enabled():
        return _fallback(), False

    rows = []
    for t in titles:
        hint = (t.overview or "").split(".")[0].strip()[:70]
        rows.append(f"{t.id}|{t.title}|{t.year}|{t.type}|{','.join(t.genres[:2])}|{hint}")

    system = (
        "A user half-remembers a movie/show: a scene, a twist, a vibe, a line — but not the "
        "title. You get the FULL catalog as rows: id|title|year|type|genres|hint. The hint is "
        "only a short logline, not the real plot — use your own knowledge of these specific, "
        "real titles (actual scenes, twists, characters, dialogue) to judge matches even when "
        "that detail isn't in the hint. Never propose an id that is not one of the given rows; "
        "if you don't recognize enough titles to judge, say so by returning fewer matches. "
        'Return JSON only: {"matches": [{"id": "<id from rows>", "confidence": 0-100, '
        '"why": "<one short, mildly spoiler-light sentence>"}]}, best first, at most 5. '
        "Be honest about confidence: use low numbers for shaky guesses. "
        'If nothing plausibly matches, return {"matches": []}.'
    )
    user = "CATALOG\n" + "\n".join(rows) + f"\n\nMEMORY\n{query}"
    data = _chat(system, user, max_tokens=500, timeout=25)
    if not isinstance(data, dict):
        return _fallback(), False
    matches = data.get("matches")
    if not isinstance(matches, list):
        return _fallback(), False

    by_id = {t.id: t for t in titles}
    out: list[dict] = []
    for m in matches:
        if not isinstance(m, dict):
            continue
        tid = m.get("id")
        if not isinstance(tid, str) or tid not in by_id:
            continue
        try:
            confidence = int(m.get("confidence", 50))
        except (TypeError, ValueError):
            confidence = 50
        confidence = max(0, min(100, confidence))
        why = str(m.get("why") or "").strip() or "Matches the description based on known plot details."
        out.append({"id": tid, "confidence": confidence, "why": why})
        if len(out) >= limit:
            break

    # An honest "nothing matches" from the model is itself a valid answer (see the app's
    # established rule: an empty result beats a fabricated near-miss), so we don't fall
    # back to embeddings just because `out` came back empty here.
    return out, True


def _digest(titles: list[Title]) -> str:
    genres, langs, people = set(), set(), []
    seen: set[str] = set()
    dual: list[str] = []
    dual_seen: set[str] = set()
    for t in titles:
        genres.update(t.genres)
        langs.update(t.languages)
        for name in t.dual_role_cast or []:
            key = name.lower()
            if key not in dual_seen:
                dual_seen.add(key)
                dual.append(name)
        for name in [*(t.cast or []), *(t.directors or [])]:
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            people.append(name)
            if len(people) >= 220:
                break
        if len(people) >= 220:
            break
    return (
        "GENRES: " + ", ".join(sorted(genres)[:40]) + "\n"
        "LANGUAGES: " + ", ".join(sorted(langs)[:30]) + "\n"
        "DUAL_ROLE: " + (", ".join(dual) if dual else "(none tagged)") + "\n"
        "PEOPLE: " + ", ".join(people)
    )


def _chat(system: str, user: str, max_tokens: int, timeout: int = 12) -> dict | None:
    _load_dotenv()
    # Defaults point at Gemini's OpenAI-compatibility endpoint (this project's
    # current provider); override OPENAI_BASE_URL/OPENAI_MODEL in .env to use
    # OpenAI or any other OpenAI-compatible endpoint instead.
    base = os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gemini-3.8-flash")
    key = os.getenv("OPENAI_API_KEY", "")
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if "generativelanguage.googleapis.com" in base:
        # Gemini 3's hidden "thinking" tokens count against max_tokens, which
        # can silently truncate replies to empty text at our small budgets.
        # Capping effort to "low" keeps enough of the budget for real output.
        payload["reasoning_effort"] = "low"
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "OpenShelf/0.1"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(base + "/chat/completions", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    try:
        text = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    return _parse_json(text)


def _parse_json(text: str) -> dict | None:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json\n", "", 1).replace("json", "", 1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _as_overlay(data: dict | None) -> dict:
    if not data:
        return {}
    allowed = set(ParsedQuery.model_fields) - {"raw"}
    out: dict = {}
    for key, value in data.items():
        if key not in allowed:
            continue
        out[key] = value
    return out
