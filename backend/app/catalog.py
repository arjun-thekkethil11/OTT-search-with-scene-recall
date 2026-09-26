from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.models import Title

_DATA = Path(__file__).resolve().parent / "data" / "catalog.json"


@lru_cache(maxsize=1)
def load_catalog() -> list[Title]:
    payload = json.loads(_DATA.read_text(encoding="utf-8"))
    return [Title.model_validate(row) for row in payload]


def facets(catalog: list[Title] | None = None) -> dict[str, list[str] | list[int]]:
    titles = catalog or load_catalog()
    genres, languages, countries, platforms, years = set(), set(), set(), set(), set()
    for t in titles:
        genres.update(t.genres)
        languages.update(t.languages)
        countries.update(t.countries)
        platforms.update(t.platforms)
        years.add(t.year)
    return {
        "genres": sorted(genres),
        "languages": sorted(languages),
        "countries": sorted(countries),
        "platforms": sorted(platforms),
        "years": sorted(years),
        "types": ["movie", "series"],
    }
