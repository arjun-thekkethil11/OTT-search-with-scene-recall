#!/usr/bin/env python3
"""Fetch fair-use poster stills from Wikipedia REST summaries."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "OpenShelf/0.1 (educational OTT catalog; https://localhost)"
CATALOG = Path(__file__).resolve().parent / "data" / "catalog.json"
PUBLIC = Path(__file__).resolve().parents[2] / "frontend" / "public"
POSTERS = PUBLIC / "posters"
BACKDROPS = PUBLIC / "backdrops"

PAGES = {
    "parasite": "Parasite_(2019_film)",
    "the-call": "The_Call_(2020_South_Korean_film)",
    "decision-to-leave": "Decision_to_Leave",
    "burning": "Burning_(2018_film)",
    "joji": "Joji_(film)",
    "badla": "Badla_(2019_film)",
    "andhadhun": "Andhadhun",
    "kill-2024": "Kill_(2023_film)",
    "drishyam-2013": "Drishyam_(2013_film)",
    "drishyam-2015": "Drishyam_(2015_film)",
    "kahaani": "Kahaani",
    "les-miserables-2019": "Les_Misérables_(2019_film)",
    "night-of-the-12th": "The_Night_of_the_12th",
    "november-2022": "November_(2022_film)",
    "anatomy-of-a-fall": "Anatomy_of_a_Fall",
    "teachers-lounge": "The_Teachers'_Lounge",
    "dogman": "Dogman_(2018_film)",
    "riders-of-justice": "Riders_of_Justice",
    "the-guilty-2018": "The_Guilty_(2018_film)",
    "another-round": "Another_Round_(film)",
    "the-platform": "The_Platform_(film)",
    "invisible-guest": "The_Invisible_Guest",
    "below-zero": "Below_Zero_(2021_film)",
    "occupant": "The_Occupant_(film)",
    "society-of-the-snow": "Society_of_the_Snow",
    "roma": "Roma_(2018_film)",
    "wild-goose-lake": "The_Wild_Goose_Lake",
    "only-the-river-flows": "Only_the_River_Flows",
    "limbo-hk": "Limbo_(2021_film)",
    "shoplifters": "Shoplifters_(film)",
    "drive-my-car": "Drive_My_Car_(film)",
    "perfect-days": "Perfect_Days",
    "confessions-2010": "Confessions_(2010_film)",
    "godzilla-minus-one": "Godzilla_Minus_One",
    "beasts-clawing": "Beasts_Clawing_at_Straws",
    "hard-hit": "Hard_Hit",
    "midnight-2021": "Midnight_(2021_film)",
    "gangster-cop-devil": "The_Gangster,_the_Cop,_the_Devil",
    "train-to-busan": "Train_to_Busan",
    "oldboy": "Oldboy_(2003_film)",
    "man-from-nowhere": "The_Man_from_Nowhere_(film)",
    "memories-of-murder": "Memories_of_Murder",
    "handmaiden": "The_Handmaiden",
    "squid-game": "Squid_Game",
    "my-name": "My_Name_(TV_series)",
    "dp": "D.P._(TV_series)",
    "beyond-evil": "Beyond_Evil",
    "dark": "Dark_(TV_series)",
    "kleo": "Kleo_(TV_series)",
    "lupin": "Lupin_(TV_series)",
    "money-heist": "Money_Heist",
    "sacred-games": "Sacred_Games_(TV_series)",
    "delhi-crime": "Delhi_Crime",
    "paatal-lok": "Paatal_Lok",
    "family-man": "The_Family_Man_(Indian_TV_series)",
    "alice-in-borderland": "Alice_in_Borderland_(TV_series)",
    "shogun": "Shōgun_(2024_TV_series)",
    "gone-girl": "Gone_Girl_(film)",
    "prisoners": "Prisoners_(2013_film)",
    "zodiac": "Zodiac_(film)",
    "nightcrawler": "Nightcrawler_(film)",
    "sicario": "Sicario_(2015_film)",
    "knives-out": "Knives_Out",
    "dune-2021": "Dune_(2021_film)",
    "spiderverse": "Spider-Man:_Across_the_Spider-Verse",
    "oppenheimer": "Oppenheimer_(film)",
    "past-lives": "Past_Lives_(film)",
    "zone-of-interest": "The_Zone_of_Interest_(film)",
    "all-quiet": "All_Quiet_on_the_Western_Front_(2022_film)",
    "close-2022": "Close_(2022_film)",
    "worst-person": "The_Worst_Person_in_the_World_(film)",
    "headhunters": "Headhunters_(film)",
    "the-hunt-2012": "The_Hunt_(2012_film)",
    "about-elly": "About_Elly",
    "holy-spider": "Holy_Spider",
    "a-separation": "A_Separation",
    "capernaum": "Capernaum_(film)",
    "the-salesman": "The_Salesman_(2016_film)",
    "portrait-lady": "Portrait_of_a_Lady_on_Fire",
    "titane": "Titane",
    "raw-2016": "Raw_(film)",
    "exhuma": "Exhuma",
    "exhuma-ok": "The_Wailing_(2016_film)",
    "minari": "Minari_(film)",
    "broker": "Broker_(2022_film)",
    "broker-hunt": "Hunt_(2022_film)",
    "special-delivery": "Special_Delivery_(2022_film)",
    "emergency-declaration": "Emergency_Declaration_(film)",
    "nayattu": "Nayattu",
    "maa-2024": "Maharaja_(2024_film)",
    "vikram": "Vikram_(2022_film)",
    "kaithi": "Kaithi_(2019_film)",
    "kumbalangi": "Kumbalangi_Nights",
    "manjummel": "Manjummel_Boys",
    "kishkindha": "Kishkindha_Kaandam",
    "bramayugam": "Bramayugam",
    "super-deluxe": "Super_Deluxe_(film)",
    "joker-2019": "Joker_(2019_film)",
    "the-batman": "The_Batman_(film)",
    "everything-everywhere": "Everything_Everywhere_All_at_Once",
    "banshees": "The_Banshees_of_Inisherin",
    "aftersun": "Aftersun",
    "tár": "Tár",
    "triangle-sadness": "Triangle_of_Sadness",
}


def _request(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read()


def summary(page: str) -> dict | None:
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(page)
    try:
        return json.loads(_request(url).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in {404, 400}:
            return None
        raise


def candidates(row: dict) -> list[str]:
    named = PAGES.get(row["id"])
    title = row["title"].replace(" ", "_")
    year = row["year"]
    kind = "TV_series" if row.get("type") == "series" else "film"
    opts = []
    if named:
        opts.append(named)
    opts.extend(
        [
            f"{title}_({year}_{kind})",
            f"{title}_({kind})",
            f"{title}_({year})",
            title,
        ]
    )
    seen: set[str] = set()
    unique: list[str] = []
    for item in opts:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def main() -> None:
    POSTERS.mkdir(parents=True, exist_ok=True)
    BACKDROPS.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    filled = 0
    for i, row in enumerate(catalog):
        dest = POSTERS / f"{row['id']}.jpg"
        if dest.exists() and dest.stat().st_size > 1500:
            row["poster_url"] = f"/posters/{dest.name}"
            bg = BACKDROPS / dest.name
            row["backdrop_url"] = f"/backdrops/{dest.name}" if bg.exists() else row["poster_url"]
            filled += 1
            continue
        image = None
        for page in candidates(row):
            try:
                data = summary(page)
            except urllib.error.HTTPError as exc:
                print(f"http {row['id']} {page}: {exc.code}")
                time.sleep(1.2)
                continue
            if not data:
                continue
            image = (data.get("originalimage") or {}).get("source") or (data.get("thumbnail") or {}).get("source")
            if image:
                break
            time.sleep(0.12)
        if not image:
            print(f"{i + 1}/{len(catalog)} {row['title']} -> none")
            continue
        image = image.split("?")[0]
        try:
            payload = _request(image)
            dest.write_bytes(payload)
            (BACKDROPS / dest.name).write_bytes(payload)
            row["poster_url"] = f"/posters/{dest.name}"
            row["backdrop_url"] = f"/backdrops/{dest.name}"
            filled += 1
            print(f"{i + 1}/{len(catalog)} {row['title']}")
        except Exception as exc:  # noqa: BLE001
            print(f"dl {row['id']}: {exc}")
        time.sleep(0.2)
    CATALOG.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"posters: {filled}/{len(catalog)}")


if __name__ == "__main__":
    main()
