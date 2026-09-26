#!/usr/bin/env python3
"""Fill catalog cast lists from Wikidata, with overrides for known titles."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = "OpenShelf/0.1 (educational OTT catalog; https://localhost)"
CATALOG = Path(__file__).resolve().parent / "data" / "catalog.json"

# Credits we already know — used when Wikidata misses, not as the search algorithm.
OVERRIDES: dict[str, list[str]] = {
    "drishyam-2013": ["Mohanlal", "Meena", "Ansiba Hassan", "Esther Anil"],
    "drishyam-2-ml": ["Mohanlal", "Meena", "Ansiba Hassan"],
    "lucifer-2019": ["Mohanlal", "Vivek Oberoi", "Manju Warrier"],
    "2018-film": ["Tovino Thomas", "Kunchacko Boban", "Asif Ali"],
    "ayyappanum-koshiyum": ["Prithviraj Sukumaran", "Biju Menon"],
    "bheeshma-parvam": ["Mammootty", "Soubin Shahir", "Shine Tom Chacko", "Sreenath Bhasi"],
    "manichitrathazhu": ["Shobana", "Mohanlal", "Suresh Gopi"],
    "malik": ["Fahadh Faasil", "Nimisha Sajayan"],
    "fight-club": ["Brad Pitt", "Edward Norton", "Helena Bonham Carter"],
    "se7en": ["Brad Pitt", "Morgan Freeman", "Gwyneth Paltrow"],
    "once-upon-hollywood": ["Leonardo DiCaprio", "Brad Pitt", "Margot Robbie"],
    "oceans-eleven": ["George Clooney", "Brad Pitt", "Julia Roberts"],
    "inglourious-basterds": ["Brad Pitt", "Mélanie Laurent", "Christoph Waltz"],
    "moneyball": ["Brad Pitt", "Jonah Hill", "Philip Seymour Hoffman"],
    "world-war-z": ["Brad Pitt", "Mireille Enos"],
    "fury-2014": ["Brad Pitt", "Shia LaBeouf", "Logan Lerman"],
    "fifty-shades": ["Dakota Johnson", "Jamie Dornan"],
    "the-lost-daughter": ["Olivia Colman", "Dakota Johnson", "Jessie Buckley"],
    "persuasion-2022": ["Dakota Johnson", "Cosmo Jarvis"],
    "cha-cha-real-smooth": ["Cooper Raiff", "Dakota Johnson"],
    "materialists": ["Dakota Johnson", "Pedro Pascal", "Chris Evans"],
    "madame-web": ["Dakota Johnson", "Sydney Sweeney"],
    "oppenheimer": ["Cillian Murphy", "Emily Blunt", "Robert Downey Jr.", "Matt Damon"],
    "inception": ["Leonardo DiCaprio", "Joseph Gordon-Levitt", "Elliot Page"],
    "interstellar": ["Matthew McConaughey", "Anne Hathaway", "Jessica Chastain"],
    "parasite": ["Song Kang-ho", "Choi Woo-shik", "Park So-dam", "Lee Sun-kyun"],
    "rrr": ["N. T. Rama Rao Jr.", "Ram Charan", "Alia Bhatt"],
}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wikidata_cast(title: str, year: int) -> list[str]:
    q = urllib.parse.urlencode(
        {
            "action": "wbsearchentities",
            "search": f"{title} {year}",
            "language": "en",
            "type": "item",
            "limit": 6,
            "format": "json",
        }
    )
    hits = _get("https://www.wikidata.org/w/api.php?" + q).get("search") or []
    if not hits:
        q = urllib.parse.urlencode(
            {
                "action": "wbsearchentities",
                "search": title,
                "language": "en",
                "type": "item",
                "limit": 6,
                "format": "json",
            }
        )
        hits = _get("https://www.wikidata.org/w/api.php?" + q).get("search") or []
    ids = [h["id"] for h in hits if h.get("id")]
    if not ids:
        return []
    get = urllib.parse.urlencode(
        {
            "action": "wbgetentities",
            "ids": "|".join(ids[:5]),
            "props": "claims|labels",
            "languages": "en",
            "format": "json",
        }
    )
    entities = _get("https://www.wikidata.org/w/api.php?" + get).get("entities") or {}
    film_types = {"Q11424", "Q24856", "Q5398426", "Q15416", "Q506240"}
    actor_ids: list[str] = []
    for ent in entities.values():
        claims = ent.get("claims") or {}
        kinds = []
        for c in claims.get("P31", []):
            kinds.append(((c.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("id"))
        if kinds and not (set(kinds) & film_types):
            continue
        years = []
        for c in claims.get("P577", []):
            t = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("time", "")
            if len(t) >= 5:
                try:
                    years.append(int(t[1:5]))
                except ValueError:
                    pass
        if years and not any(abs(y - year) <= 1 for y in years):
            continue
        for c in claims.get("P161", []):
            aid = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("id")
            if aid:
                actor_ids.append(aid)
        if actor_ids:
            break
    if not actor_ids:
        return []
    labels_q = urllib.parse.urlencode(
        {
            "action": "wbgetentities",
            "ids": "|".join(actor_ids[:10]),
            "props": "labels",
            "languages": "en",
            "format": "json",
        }
    )
    actors = _get("https://www.wikidata.org/w/api.php?" + labels_q).get("entities") or {}
    names = []
    for aid in actor_ids[:8]:
        label = ((actors.get(aid) or {}).get("labels") or {}).get("en", {}).get("value")
        if label and label not in names:
            names.append(label)
    return names


def merge(existing: list[str], extra: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for name in [*existing, *extra]:
        key = name.strip()
        if not key or key.lower() in seen:
            continue
        seen.add(key.lower())
        out.append(key)
    return out


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    fetched = 0
    for row in catalog:
        row.setdefault("cast", [])
        before = list(row["cast"])
        if row["id"] in OVERRIDES:
            row["cast"] = merge(row["cast"], OVERRIDES[row["id"]])
        if len(row["cast"]) >= 2:
            continue
        try:
            names = wikidata_cast(row["title"], int(row["year"]))
            if names:
                row["cast"] = merge(row["cast"], names)
                fetched += 1
                print(f"  {row['title']}: {', '.join(row['cast'][:5])}")
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {row['id']}: {exc}")
        if row["cast"] != before:
            pass
        time.sleep(0.15)
    CATALOG.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    with_cast = sum(1 for r in catalog if r.get("cast"))
    print(f"wikidata filled {fetched}; {with_cast}/{len(catalog)} titles have cast")


if __name__ == "__main__":
    main()
