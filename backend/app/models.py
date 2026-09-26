from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Title(BaseModel):
    id: str
    title: str
    year: int
    runtime_min: int | None = None
    type: Literal["movie", "series"] = "movie"
    seasons: int | None = None
    genres: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    imdb: float | None = None
    overview: str = ""
    themes: list[str] = Field(default_factory=list)
    directors: list[str] = Field(default_factory=list)
    cast: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    poster_hue: int = 200
    poster_url: str | None = None
    backdrop_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    remake_of: str | None = None
    dual_role_cast: list[str] = Field(default_factory=list)


class ParsedQuery(BaseModel):
    raw: str
    runtime_min: int | None = None
    runtime_max: int | None = None
    year_min: int | None = None
    year_max: int | None = None
    imdb_min: float | None = None
    imdb_max: float | None = None
    genres_include: list[str] = Field(default_factory=list)
    genres_exclude: list[str] = Field(default_factory=list)
    languages_include: list[str] = Field(default_factory=list)
    languages_exclude: list[str] = Field(default_factory=list)
    non_english: bool = False
    countries_include: list[str] = Field(default_factory=list)
    types: list[str] = Field(default_factory=list)
    platforms_include: list[str] = Field(default_factory=list)
    people_include: list[str] = Field(default_factory=list)
    dual_role: bool = False
    semantic_text: str = ""


class MatchReason(BaseModel):
    kind: Literal["filter", "semantic", "miss"]
    label: str
    detail: str


class SearchHit(BaseModel):
    title: Title
    score: float
    semantic: float
    match_percent: int = 0
    reasons: list[MatchReason]


class SearchRequest(BaseModel):
    query: str
    limit: int = 20


class SearchResponse(BaseModel):
    query: str
    parsed: ParsedQuery
    results: list[SearchHit]
    near_misses: list[SearchHit]
    catalog_size: int


class RecallHit(BaseModel):
    title: Title
    confidence: int
    why: str


class RecallResponse(BaseModel):
    query: str
    hits: list[RecallHit]
    ai_used: bool
