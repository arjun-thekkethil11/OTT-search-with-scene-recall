from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher, get_close_matches
from typing import TYPE_CHECKING

from app.models import ParsedQuery
from app.nlp import extract_person_names, ner_available

if TYPE_CHECKING:
    from app.models import Title

GENRE_ALIASES: dict[str, str] = {
    "thriller": "Thriller",
    "crime": "Crime",
    "mystery": "Mystery",
    "noir": "Noir",
    "neo-noir": "Noir",
    "action": "Action",
    "drama": "Drama",
    "comedy": "Comedy",
    "horror": "Horror",
    "sci-fi": "Sci-Fi",
    "science fiction": "Sci-Fi",
    "scifi": "Sci-Fi",
    "romance": "Romance",
    "romantic": "Romance",
    "animation": "Animation",
    "anime": "Animation",
    "documentary": "Documentary",
    "doc": "Documentary",
    "war": "War",
    "western": "Western",
    "fantasy": "Fantasy",
    "adventure": "Adventure",
    "family": "Family",
    "history": "History",
    "historical": "History",
    "biography": "Biography",
    "biopic": "Biography",
    "sport": "Sport",
    "musical": "Musical",
    "music": "Music",
    "superhero": "Superhero",
    "heist": "Heist",
    "political": "Politics",
    "politics": "Politics",
    "spy": "Spy",
    "espionage": "Spy",
}

LANGUAGE_ALIASES: dict[str, str] = {
    "english": "English",
    "korean": "Korean",
    "k-drama": "Korean",
    "kdrama": "Korean",
    "japanese": "Japanese",
    "hindi": "Hindi",
    "bollywood": "Hindi",
    "tamil": "Tamil",
    "kollywood": "Tamil",
    "malayalam": "Malayalam",
    "mollywood": "Malayalam",
    "telugu": "Telugu",
    "tollywood": "Telugu",
    "spanish": "Spanish",
    "french": "French",
    "german": "German",
    "italian": "Italian",
    "portuguese": "Portuguese",
    "brazilian": "Portuguese",
    "mandarin": "Mandarin",
    "chinese": "Mandarin",
    "cantonese": "Cantonese",
    "thai": "Thai",
    "turkish": "Turkish",
    "arabic": "Arabic",
    "persian": "Persian",
    "farsi": "Persian",
    "swedish": "Swedish",
    "danish": "Danish",
    "norwegian": "Norwegian",
    "finnish": "Finnish",
    "icelandic": "Icelandic",
    "polish": "Polish",
    "russian": "Russian",
    "dutch": "Dutch",
    "greek": "Greek",
    "hebrew": "Hebrew",
    "indonesian": "Indonesian",
    "filipino": "Filipino",
    "tagalog": "Filipino",
}

COUNTRY_ALIASES: dict[str, str] = {
    "korea": "South Korea",
    "south korea": "South Korea",
    "korean": "South Korea",
    "japan": "Japan",
    "india": "India",
    "indian": "India",
    "france": "France",
    "french": "France",
    "spain": "Spain",
    "spanish": "Spain",
    "germany": "Germany",
    "german": "Germany",
    "italy": "Italy",
    "italian": "Italy",
    "uk": "United Kingdom",
    "britain": "United Kingdom",
    "british": "United Kingdom",
    "usa": "United States",
    "us": "United States",
    "american": "United States",
    "hollywood": "United States",
    "mexico": "Mexico",
    "brazil": "Brazil",
    "china": "China",
    "hong kong": "Hong Kong",
    "taiwan": "Taiwan",
    "sweden": "Sweden",
    "denmark": "Denmark",
    "norway": "Norway",
    "iceland": "Iceland",
    "turkey": "Turkey",
    "iran": "Iran",
    "argentina": "Argentina",
    "chile": "Chile",
}

PLATFORM_ALIASES: dict[str, str] = {
    "netflix": "Netflix",
    "prime": "Prime Video",
    "amazon": "Prime Video",
    "prime video": "Prime Video",
    "disney": "Disney+",
    "disney+": "Disney+",
    "hulu": "Hulu",
    "hbo": "Max",
    "max": "Max",
    "apple": "Apple TV+",
    "apple tv": "Apple TV+",
    "hotstar": "JioHotstar",
    "jiohotstar": "JioHotstar",
    "sony liv": "SonyLIV",
    "sonyliv": "SonyLIV",
    "zee5": "ZEE5",
    "crunchyroll": "Crunchyroll",
    "mubi": "MUBI",
}

DASH = r"[\-–—to]+"


@dataclass
class _Span:
    start: int
    end: int


def parse_query(raw: str, catalog: list[Title] | None = None) -> ParsedQuery:
    text = (raw or "").strip().replace("–", "-").replace("—", "-")
    lower = text.lower()
    consumed: list[_Span] = []

    def eat(match: re.Match[str] | None) -> str | None:
        if not match:
            return None
        consumed.append(_Span(*match.span()))
        return match.group(0)

    runtime_min = runtime_max = None
    year_min = year_max = None
    imdb_min = imdb_max = None
    genres_include: list[str] = []
    genres_exclude: list[str] = []
    languages_include: list[str] = []
    languages_exclude: list[str] = []
    countries_include: list[str] = []
    platforms_include: list[str] = []
    types: list[str] = []
    non_english = False
    dual_role = False

    match = re.search(rf"((?:19|20)\d{{2}})\s*{DASH}\s*((?:19|20)\d{{2}})", lower)
    if match:
        eat(match)
        a, b = int(match.group(1)), int(match.group(2))
        year_min, year_max = min(a, b), max(a, b)

    match = re.search(r"(?:released\s+)?after\s+((?:19|20)\d{2})", lower)
    if match:
        eat(match)
        year_min = int(match.group(1)) + 1

    match = re.search(r"(?:released\s+)?(?:since|from|starting(?: in)?)\s+((?:19|20)\d{2})", lower)
    if match and year_min is None:
        eat(match)
        year_min = int(match.group(1))

    match = re.search(r"(?:released\s+)?(?:before|earlier than)\s+((?:19|20)\d{2})", lower)
    if match:
        eat(match)
        year_max = int(match.group(1)) - 1

    decade = re.search(r"\b(?:the\s+)?(\d{2}|19\d{2}|20\d{2})s\b", lower)
    if decade:
        eat(decade)
        token = decade.group(1)
        if len(token) == 2:
            century = 1900 if int(token) >= 40 else 2000
            start = century + int(token)
        else:
            start = int(token)
        year_min, year_max = start, start + 9

    for match in re.finditer(
        rf"(?:runtime|run\s*time|length|duration)?\s*"
        rf"(\d{{2,3}})\s*{DASH}\s*(\d{{2,3}})\s*(?:min(?:ute)?s?|hrs?|hours?)?",
        lower,
    ):
        if _overlaps(match.span(), consumed):
            continue
        a, b = int(match.group(1)), int(match.group(2))
        if a >= 1800 or b >= 1800 or max(a, b) > 400:
            continue
        eat(match)
        runtime_min, runtime_max = min(a, b), max(a, b)
        if match.group(0).endswith("hr") or "hour" in match.group(0):
            runtime_min, runtime_max = runtime_min * 60, runtime_max * 60

    for pattern, lo, hi in (
        (r"(?:under|less than|shorter than|<)\s*(\d{1,3})\s*(min(?:ute)?s?)", True, False),
        (r"(?:over|more than|at least|longer than|>)\s*(\d{1,3})\s*(min(?:ute)?s?)", False, True),
        (r"(?:under|less than|<)\s*(\d)\s*(?:hrs?|hours?)", True, False),
        (r"(?:over|more than|at least|>)\s*(\d)\s*(?:hrs?|hours?)", False, True),
        (r"(?:about|around|~|approx(?:imately)?)\s*(\d{2,3})\s*min", False, False),
    ):
        match = re.search(pattern, lower)
        if match:
            eat(match)
            n = int(match.group(1))
            if "hour" in match.group(0) or match.group(0).rstrip("s").endswith("hr"):
                n *= 60
            if lo and not hi:
                runtime_max = n
            elif hi and not lo:
                runtime_min = n
            else:
                runtime_min, runtime_max = max(n - 15, 1), n + 15

    if re.search(r"\bshort films?\b|\bshorts\b", lower):
        match = re.search(r"\bshort films?\b|\bshorts\b", lower)
        eat(match)
        runtime_max = runtime_max or 40

    match = re.search(
        r"(?:imdb|rating)\s*(?:of\s*)?(?:below|under|less than|at most|max(?:imum)?|<=|<)\s*(\d(?:\.\d)?)",
        lower,
    )
    if match:
        eat(match)
        imdb_max = float(match.group(1))

    match = re.search(
        r"(?:below|under|less than|at most|no more than|max(?:imum)?)\s*(\d(?:\.\d)?)\s*(?:on\s+)?(?:imdb|rating)",
        lower,
    )
    if match and imdb_max is None:
        eat(match)
        imdb_max = float(match.group(1))

    match = re.search(r"(?:below|under|less than)\s*(\d(?:\.\d)?)\s*(?:imdb|rating)", lower)
    if match and imdb_max is None:
        eat(match)
        imdb_max = float(match.group(1))

    match = re.search(r"imdb\s*(?:below|under|<|<=)\s*(\d(?:\.\d)?)", lower)
    if match and imdb_max is None:
        eat(match)
        imdb_max = float(match.group(1))

    match = re.search(
        r"(?:imdb|rating|rated)\s*(?:of\s*)?(>=|>|at least|over|above|minimum|min\.?)?\s*(\d(?:\.\d)?)",
        lower,
    )
    if match and not _overlaps(match.span(), consumed):
        eat(match)
        value = float(match.group(2))
        op = (match.group(1) or ">").strip()
        imdb_min = value if op in {">=", "at least", "minimum", "min."} else value + 0.01 if op in {">", "over", "above"} else value
        if op in {">", "over", "above"} or (match.group(1) is None and ">" in match.group(0)):
            imdb_min = value + 1e-6
        elif match.group(1) is None:
            imdb_min = value

    match = re.search(r"(>=|>)\s*(\d(?:\.\d)?)\s*(?:on\s+)?imdb", lower)
    if match:
        eat(match)
        value = float(match.group(2))
        imdb_min = value if match.group(1) == ">=" else value + 1e-6

    match = re.search(r"imdb\s*>\s*(\d(?:\.\d)?)", lower)
    if match:
        eat(match)
        imdb_min = float(match.group(1)) + 1e-6

    match = re.search(r"imdb\s*>=\s*(\d(?:\.\d)?)", lower)
    if match:
        eat(match)
        imdb_min = float(match.group(1))

    if re.search(r"\b(series|tv show|shows|limited series|miniseries)\b", lower) and not re.search(
        r"\b(movies?|films?)\b", lower
    ):
        types.append("series")
        for m in re.finditer(r"\b(series|tv show|shows|limited series|miniseries)\b", lower):
            eat(m)
    elif re.search(r"\b(movies?|films?)\b", lower) and not re.search(r"\b(series|tv show)\b", lower):
        types.append("movie")
        for m in re.finditer(r"\b(movies?|films?)\b", lower):
            eat(m)

    for m in re.finditer(
        r"\b(?:double roles?|dual roles?|twin roles?|two roles|two characters|"
        r"multiple roles|double acting|dual acting|double role play)\b",
        lower,
    ):
        eat(m)
        dual_role = True
    if re.search(r"\b(?:plays?|playing|does|did)\s+(?:a\s+)?(?:double|dual)\s+role\b", lower):
        m = re.search(r"\b(?:plays?|playing|does|did)\s+(?:a\s+)?(?:double|dual)\s+role\b", lower)
        eat(m)
        dual_role = True

    if re.search(r"\b(non[-\s]?english|not english|foreign(?:[-\s]language)?|other than english)\b", lower):
        non_english = True
        languages_exclude.append("English")
        for m in re.finditer(r"\b(non[-\s]?english|not english|foreign(?:[-\s]language)?|other than english)\b", lower):
            eat(m)

    exclude_prefixes = r"(?:no|not|without|exclude(?:ing)?|except|-)\s+"

    for alias, canonical in sorted(GENRE_ALIASES.items(), key=lambda x: -len(x[0])):
        for m in re.finditer(rf"{exclude_prefixes}{re.escape(alias)}\b", lower):
            eat(m)
            if canonical not in genres_exclude:
                genres_exclude.append(canonical)
        for m in re.finditer(rf"\b{re.escape(alias)}\b", lower):
            if _overlaps(m.span(), consumed):
                continue
            eat(m)
            if canonical not in genres_include and canonical not in genres_exclude:
                genres_include.append(canonical)

    for tok_match in re.finditer(r"[a-z]{5,}", lower):
        if _overlaps(tok_match.span(), consumed):
            continue
        token = tok_match.group(0)
        if token in GENRE_ALIASES or token in {
            "movies", "movie", "films", "film", "series", "shows", "rating", "rated",
            "imdb", "english", "hours", "minutes", "something", "anything", "below",
            "above", "under", "thriller",
        }:
            continue
        close = get_close_matches(token, list(GENRE_ALIASES), n=1, cutoff=0.78)
        if not close:
            continue
        canonical = GENRE_ALIASES[close[0]]
        if SequenceMatcher(None, token, close[0]).ratio() < 0.78:
            continue
        eat(tok_match)
        if canonical not in genres_include and canonical not in genres_exclude:
            genres_include.append(canonical)

    for alias, canonical in sorted(LANGUAGE_ALIASES.items(), key=lambda x: -len(x[0])):
        for m in re.finditer(rf"{exclude_prefixes}{re.escape(alias)}\b", lower):
            eat(m)
            if canonical not in languages_exclude:
                languages_exclude.append(canonical)
        pattern = rf"(?:in\s+)?{re.escape(alias)}(?:[-\s]language)?"
        for m in re.finditer(rf"\b{pattern}\b", lower):
            if _overlaps(m.span(), consumed):
                continue
            eat(m)
            if canonical == "English" and non_english:
                continue
            if canonical not in languages_include and canonical not in languages_exclude:
                languages_include.append(canonical)

    for alias, canonical in sorted(COUNTRY_ALIASES.items(), key=lambda x: -len(x[0])):
        for m in re.finditer(rf"\b(?:from|made in|set in|country)\s+{re.escape(alias)}\b", lower):
            if _overlaps(m.span(), consumed):
                continue
            eat(m)
            if canonical not in countries_include:
                countries_include.append(canonical)

    for alias, canonical in sorted(PLATFORM_ALIASES.items(), key=lambda x: -len(x[0])):
        for m in re.finditer(rf"\b{re.escape(alias)}\b", lower):
            if _overlaps(m.span(), consumed):
                continue
            eat(m)
            if canonical not in platforms_include:
                platforms_include.append(canonical)

    people_include: list[str] = []
    for pattern in (
        rf"(?:starring|featuring|feat\.?|actor|actress)\s+([a-z][a-z .'\-]+)",
        rf"(?:directed by|director)\s+([a-z][a-z .'\-]+)",
        rf"(?:movies?|films?|shows?|series|titles?)\s+(?:by|of|from)\s+([a-z][a-z .'\-]+)",
        rf"([a-z][a-z .'\-]+?)\s+(?:movies?|films?|shows?|series|titles?)\b",
    ):
        for m in re.finditer(pattern, lower):
            if _overlaps(m.span(), consumed):
                continue
            name = _clean_person(m.group(1))
            if not name:
                continue
            eat(m)
            if name not in people_include:
                people_include.append(name)

    # spaCy NER on original casing (capitalization is the signal). Skip if the model is missing.
    if ner_available():
        for name in extract_person_names(text):
            m = re.search(re.escape(name.lower()), lower)
            if not m or _overlaps(m.span(), consumed):
                continue
            eat(m)
            if name not in people_include:
                people_include.append(name)

    semantic = _remainder(text, consumed)
    semantic = re.sub(r"\b(give me|find|show|watch|looking for|i want|please|a|an|the|with|and)\b", " ", semantic, flags=re.I)
    semantic = re.sub(r"\s+", " ", semantic).strip(" ,.")
    leftover_name = _clean_person(semantic)
    if leftover_name and _looks_like_person(leftover_name) and leftover_name not in people_include:
        if types or people_include or dual_role:
            people_include.append(leftover_name)

    if imdb_min is not None and imdb_max is not None and imdb_min > imdb_max:
        imdb_min = None

    return ParsedQuery(
        raw=text,
        runtime_min=runtime_min,
        runtime_max=runtime_max,
        year_min=year_min,
        year_max=year_max,
        imdb_min=imdb_min,
        imdb_max=imdb_max,
        genres_include=_unique(genres_include),
        genres_exclude=_unique(genres_exclude),
        languages_include=_unique(languages_include),
        languages_exclude=_unique(languages_exclude),
        non_english=non_english,
        countries_include=_unique(countries_include),
        types=_unique(types),
        platforms_include=_unique(platforms_include),
        people_include=_unique(people_include),
        dual_role=dual_role,
        semantic_text=semantic,
    )
    if catalog:
        parsed = _merge_ai(parsed, catalog)
    return parsed


def _merge_ai(parsed: ParsedQuery, catalog: list[Title]) -> ParsedQuery:
    try:
        from app.ai_intent import interpret_query
    except Exception:  # noqa: BLE001
        return parsed
    overlay = interpret_query(parsed.raw, catalog)
    if not overlay:
        return parsed
    data = parsed.model_dump()
    for key, value in overlay.items():
        if value is None or value == [] or value == "":
            continue
        data[key] = value
    data["raw"] = parsed.raw
    try:
        return ParsedQuery.model_validate(data)
    except Exception:  # noqa: BLE001
        return parsed


def _overlaps(span: tuple[int, int], consumed: list[_Span]) -> bool:
    s, e = span
    return any(not (e <= c.start or s >= c.end) for c in consumed)


def _remainder(text: str, consumed: list[_Span]) -> str:
    chars = list(text)
    for span in consumed:
        for i in range(span.start, min(span.end, len(chars))):
            chars[i] = " "
    return "".join(chars)


def _clean_person(raw: str) -> str:
    text = re.sub(r"\s+", " ", (raw or "").strip(" .,!?:;"))
    text = re.sub(
        r"\b(starring|featuring|feat|movies?|films?|shows?|series|titles?|directed|director|"
        r"by|of|from|in|which|who|whom|whose|does|did|doing|plays?|playing|that|has|have|"
        r"with|where|some|any|his|her|their|a|an|the)\b",
        " ",
        text,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", text).strip(" .,")


def _looks_like_person(name: str) -> bool:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z'.\-]*", name)
    if not tokens or len(tokens) > 4:
        return False
    blocked = set(GENRE_ALIASES) | set(LANGUAGE_ALIASES) | set(COUNTRY_ALIASES) | set(PLATFORM_ALIASES) | {
        "best",
        "good",
        "new",
        "old",
        "like",
        "similar",
        "something",
        "anything",
        "stuff",
        "watch",
        "recommend",
        "recommendation",
        "catalog",
        "top",
        "latest",
        "recent",
        "classic",
        "must",
        "see",
    }
    return all(tok.lower() not in blocked and not tok.isdigit() for tok in tokens)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
