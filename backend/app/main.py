from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.catalog import facets, load_catalog
from app.models import ParsedQuery, RecallHit, RecallResponse, SearchRequest, SearchResponse, Title
from app.parser import parse_query
from app.search import SemanticIndex, search as run_search
from app.ai_intent import recall_scene, refine_hits

app = FastAPI(title="OpenShelf", version="0.1.0", description="Personal OTT search.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _warm_models() -> None:
    _index()  # warm embeddings + NER before the first request


@lru_cache(maxsize=1)
def _index() -> SemanticIndex:
    return SemanticIndex(load_catalog())


@app.get("/api/health")
def health() -> dict[str, str | int]:
    return {"status": "ok", "titles": len(load_catalog())}


@app.get("/api/facets")
def get_facets() -> dict:
    return facets()


@app.get("/api/titles")
def list_titles(
    genre: str | None = None,
    language: str | None = None,
    country: str | None = None,
    year: int | None = None,
    platform: str | None = None,
    type: str | None = Query(default=None, alias="type"),
    q: str | None = None,
) -> list[Title]:
    rows = load_catalog()
    if genre:
        rows = [t for t in rows if genre in t.genres]
    if language:
        rows = [t for t in rows if language in t.languages]
    if country:
        rows = [t for t in rows if country in t.countries]
    if year:
        rows = [t for t in rows if t.year == year]
    if platform:
        rows = [t for t in rows if platform in t.platforms]
    if type:
        rows = [t for t in rows if t.type == type]
    if q:
        needle = q.lower()
        rows = [
            t
            for t in rows
            if needle in t.title.lower()
            or needle in t.overview.lower()
            or any(needle in x.lower() for x in t.themes)
            or any(needle in x.lower() for x in t.cast)
            or any(needle in x.lower() for x in t.directors)
        ]
    return rows


@app.post("/api/parse", response_model=ParsedQuery)
def parse_endpoint(body: SearchRequest) -> ParsedQuery:
    return parse_query(body.query, catalog=load_catalog())


@app.post("/api/search", response_model=SearchResponse)
def search_endpoint(body: SearchRequest) -> SearchResponse:
    titles = load_catalog()
    parsed = parse_query(body.query, catalog=titles)
    results, near = run_search(titles, parsed, _index(), limit=body.limit)
    refined = refine_hits(body.query, results, body.limit)
    if refined is not None:
        results = refined
    return SearchResponse(
        query=body.query,
        parsed=parsed,
        results=results,
        near_misses=near,
        catalog_size=len(titles),
    )


@app.post("/api/recall", response_model=RecallResponse)
def recall_endpoint(body: SearchRequest) -> RecallResponse:
    titles = load_catalog()
    by_id = {t.id: t for t in titles}
    raw_hits, ai_used = recall_scene(body.query, titles, _index(), limit=body.limit or 6)
    hits = [
        RecallHit(title=by_id[h["id"]], confidence=h["confidence"], why=h["why"])
        for h in raw_hits
        if h["id"] in by_id
    ]
    return RecallResponse(query=body.query, hits=hits, ai_used=ai_used)
