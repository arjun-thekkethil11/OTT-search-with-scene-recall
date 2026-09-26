from __future__ import annotations

import math
import re
from collections import Counter
from difflib import SequenceMatcher

from app.models import MatchReason, ParsedQuery, SearchHit, Title
from app.nlp import embeddings_available, encode

TOKEN = re.compile(r"[a-z0-9]+")
ENGLISH = {"english"}


class SemanticIndex:
    """TF-IDF plus sentence embeddings when available; TF-IDF only if they don't load."""

    def __init__(self, titles: list[Title]) -> None:
        self.titles = titles
        docs = [_document(t) for t in titles]
        self._tfidf = _fit(docs)
        self._doc_embeddings = None
        if embeddings_available() and docs:
            try:
                self._doc_embeddings = encode(docs)
            except Exception:  # noqa: BLE001
                self._doc_embeddings = None

    def scores(self, query: str) -> list[float]:
        if not query.strip():
            return [0.0] * len(self.titles)
        q = _vectorize(query, self._tfidf)
        tfidf_scores = [_cosine(q, doc) for doc in self._tfidf["docs"]]
        if self._doc_embeddings is None:
            return tfidf_scores
        try:
            q_emb = encode([query])[0]
        except Exception:  # noqa: BLE001
            return tfidf_scores
        emb_scores = self._doc_embeddings @ q_emb
        return [
            0.55 * t + 0.45 * max(float(e), 0.0)
            for t, e in zip(tfidf_scores, emb_scores)
        ]


def search(
    titles: list[Title],
    parsed: ParsedQuery,
    index: SemanticIndex,
    limit: int = 20,
) -> tuple[list[SearchHit], list[SearchHit]]:
    semantic_query = " ".join(
        [
            parsed.semantic_text,
            " ".join(parsed.genres_include),
            parsed.raw,
        ]
    ).strip()
    semantic_scores = index.scores(semantic_query)

    people = _resolve_people(titles, parsed)
    person_requested = bool(parsed.people_include)
    matched: list[SearchHit] = []
    misses: list[SearchHit] = []

    for title, sem in zip(titles, semantic_scores):
        reasons, failed = _evaluate(title, parsed, sem, people)
        fuzzy = max(_fuzzy_title(parsed.raw, title), _fuzzy_title(parsed.semantic_text, title))
        person_hit = _credit_match(title, people)
        if fuzzy >= 0.78:
            reasons.insert(0, MatchReason(kind="filter", label="Title", detail=title.title))
        score = _rank_score(title, parsed, sem, failed, fuzzy, person_hit)
        hit = SearchHit(
            title=title,
            score=round(score, 4),
            semantic=round(sem, 4),
            match_percent=_match_percent(parsed, failed, sem, fuzzy, bool(people)),
            reasons=reasons,
        )
        type_ok = not parsed.types or title.type in parsed.types
        title_hit = fuzzy >= 0.78 and type_ok and "Dual role" not in failed
        if failed and not title_hit:
            if person_requested and not person_hit:
                continue
            if parsed.dual_role and "Dual role" in failed:
                continue
            if len(failed) <= 2 and (sem >= 0.04 or fuzzy >= 0.7 or person_hit):
                misses.append(hit)
        else:
            matched.append(hit)

    matched.sort(key=lambda h: h.score, reverse=True)
    misses.sort(key=lambda h: (len([r for r in h.reasons if r.kind == "miss"]), -h.score))
    return matched[:limit], misses[: min(8, limit)]


def _evaluate(
    title: Title, q: ParsedQuery, semantic: float, people: list[str]
) -> tuple[list[MatchReason], list[str]]:
    reasons: list[MatchReason] = []
    failed: list[str] = []

    def ok(cond: bool, label: str, good: str, bad: str) -> None:
        if cond:
            reasons.append(MatchReason(kind="filter", label=label, detail=good))
        else:
            failed.append(label)
            reasons.append(MatchReason(kind="miss", label=label, detail=bad))

    if q.runtime_min is not None or q.runtime_max is not None:
        lo, hi = q.runtime_min or 0, q.runtime_max or 10_000
        runtime = title.runtime_min
        if runtime is None:
            ok(title.type == "series", "Runtime", "Series", "No runtime on file")
        else:
            ok(lo <= runtime <= hi, "Runtime", f"{runtime} min", f"{runtime} min")

    if q.year_min is not None or q.year_max is not None:
        lo, hi = q.year_min or 0, q.year_max or 3000
        ok(lo <= title.year <= hi, "Year", str(title.year), str(title.year))

    if q.imdb_min is not None or q.imdb_max is not None:
        if title.imdb is None:
            ok(False, "IMDB", "", "No rating on file")
        else:
            lo = q.imdb_min if q.imdb_min is not None else 0.0
            hi = q.imdb_max if q.imdb_max is not None else 10.0
            ok(lo <= title.imdb <= hi, "IMDB", f"{title.imdb:.1f}", f"{title.imdb:.1f}")

    if q.genres_include:
        overlap = [g for g in q.genres_include if g in title.genres]
        ok(bool(overlap), "Genre", ", ".join(overlap), ", ".join(title.genres))

    if q.genres_exclude:
        hit = [g for g in q.genres_exclude if g in title.genres]
        if hit:
            ok(False, "Genre", "", ", ".join(hit))

    if q.non_english or q.languages_exclude:
        langs_l = {x.lower() for x in title.languages}
        is_english_only = langs_l <= ENGLISH and bool(langs_l)
        has_non_en = any(x.lower() not in ENGLISH for x in title.languages)
        if q.non_english:
            ok(
                has_non_en and not is_english_only,
                "Language",
                ", ".join(title.languages),
                ", ".join(title.languages),
            )
        for lang in q.languages_exclude:
            if lang.lower() == "english" and q.non_english:
                continue
            ok(lang not in title.languages, "Language", f"Not {lang}", lang)

    if q.languages_include:
        overlap = [x for x in q.languages_include if x in title.languages]
        ok(bool(overlap), "Language", ", ".join(overlap), ", ".join(title.languages))

    if q.countries_include:
        overlap = [x for x in q.countries_include if x in title.countries]
        ok(bool(overlap), "Country", ", ".join(overlap), ", ".join(title.countries))

    if q.types:
        ok(title.type in q.types, "Type", title.type, title.type)

    if q.platforms_include:
        overlap = [x for x in q.platforms_include if x in title.platforms]
        ok(bool(overlap), "Platform", ", ".join(overlap), ", ".join(title.platforms) or "unknown")

    if q.people_include:
        who = _credit_match(title, people)
        if who:
            label = "Cast" if who in {n for n in title.cast} else "Director"
            reasons.append(MatchReason(kind="filter", label=label, detail=who))
        else:
            failed.append("Person")
            reasons.append(MatchReason(kind="miss", label="Person", detail="Not in credits"))

    if q.dual_role:
        names = title.dual_role_cast or []
        if people:
            who = None
            compact_map = {_compact(n): n for n in names}
            for person in people:
                if _compact(person) in compact_map:
                    who = compact_map[_compact(person)]
                    break
                for n in names:
                    if n == person:
                        who = n
                        break
            ok(bool(who), "Dual role", who or people[0], "No dual role on file")
        else:
            ok(bool(names), "Dual role", ", ".join(names[:3]) or "yes", "No dual role on file")

    if semantic >= 0.05:
        reasons.append(
            MatchReason(
                kind="semantic",
                label="About",
                detail=_semantic_why(title, q),
            )
        )

    return reasons, failed


def _rank_score(
    title: Title, q: ParsedQuery, semantic: float, failed: list[str], fuzzy: float = 0.0, person_hit: str | None = None
) -> float:
    score = 0.55 * semantic + (1.25 * fuzzy if fuzzy >= 0.78 else 0.08 * fuzzy)
    if person_hit:
        score += 1.45
    if not failed:
        score += 0.25
    if title.imdb:
        score += 0.015 * title.imdb
    if q.runtime_min is not None and q.runtime_max is not None and title.runtime_min:
        mid = (q.runtime_min + q.runtime_max) / 2
        dist = abs(title.runtime_min - mid) / max(q.runtime_max - q.runtime_min, 1)
        score += max(0.0, 0.12 * (1 - dist))
    if failed and fuzzy < 0.78:
        score -= 0.18 * len(failed)
    return max(score, 0.0)


def _match_percent(
    q: ParsedQuery, failed: list[str], semantic: float, fuzzy: float = 0.0, people: bool = False
) -> int:
    slots = 0
    if q.runtime_min is not None or q.runtime_max is not None:
        slots += 1
    if q.year_min is not None or q.year_max is not None:
        slots += 1
    if q.imdb_min is not None or q.imdb_max is not None:
        slots += 1
    if q.genres_include or q.genres_exclude:
        slots += 1
    if q.non_english or q.languages_include or q.languages_exclude:
        slots += 1
    if q.countries_include:
        slots += 1
    if q.types:
        slots += 1
    if q.platforms_include:
        slots += 1
    if people or q.people_include:
        slots += 1
    if q.dual_role:
        slots += 1
    passed = max(slots - len(failed), 0)
    filter_ratio = 1.0 if slots == 0 else passed / slots
    semantic_ratio = min(max(semantic, 0.0) / 0.22, 1.0)
    percent = 40 * filter_ratio + 25 * semantic_ratio + 35 * min(max(fuzzy, 0.0), 1.0)
    if not failed:
        percent += 5
    return int(max(0, min(99, round(percent))))


def _credits(title: Title) -> list[str]:
    return [*(title.cast or []), *(title.directors or [])]


def _resolve_people(titles: list[Title], parsed: ParsedQuery) -> list[str]:
    names = []
    seen: set[str] = set()
    for title in titles:
        for name in _credits(title):
            key = name.lower()
            if key not in seen:
                seen.add(key)
                names.append(name)
    last_counts: Counter[str] = Counter()
    for name in names:
        toks = TOKEN.findall(name.lower())
        if toks:
            last_counts[toks[-1]] += 1

    needles = [n for n in parsed.people_include if n.strip()]
    leftover = (parsed.semantic_text or "").strip()
    if leftover and leftover.lower() not in {n.lower() for n in needles}:
        needles.append(leftover)

    resolved: list[str] = []
    for needle in needles:
        person, score = _best_person(needle, names, last_counts)
        if person and score >= 0.82 and person not in resolved:
            resolved.append(person)
    return resolved


def _best_person(needle: str, names: list[str], last_counts: Counter[str]) -> tuple[str | None, float]:
    q_tokens = [t for t in TOKEN.findall(needle.lower()) if t not in STOPWORDS and not t.isdigit()]
    if not q_tokens:
        return None, 0.0
    compact_q = _compact(" ".join(q_tokens))
    best_name = None
    best = 0.0
    unique_last = last_counts.get(q_tokens[-1], 0) == 1 if len(q_tokens) == 1 else False
    for name in names:
        n_tokens = TOKEN.findall(name.lower())
        compact_n = _compact(name)
        if not compact_n:
            continue
        score = SequenceMatcher(None, compact_q, compact_n).ratio()
        if compact_q == compact_n:
            score = 1.0
        elif len(compact_q) >= 5 and compact_q in compact_n:
            score = max(score, 0.92)
        if len(q_tokens) == 1 and unique_last and n_tokens and q_tokens[0] == n_tokens[-1]:
            score = max(score, 0.9)
        if len(q_tokens) >= 2:
            hits = 0
            for qt in q_tokens:
                tok_best = 0.0
                for nt in n_tokens:
                    if qt == nt:
                        tok_best = 1.0
                    elif abs(len(qt) - len(nt)) <= 2:
                        tok_best = max(tok_best, SequenceMatcher(None, qt, nt).ratio())
                if tok_best >= 0.8:
                    hits += 1
            if hits == len(q_tokens):
                score = max(score, 0.94)
            elif hits >= 1 and len(q_tokens) == 2:
                score = max(score, 0.7 * hits / len(q_tokens))
        if score > best:
            best = score
            best_name = name
    return best_name, best


def _credit_match(title: Title, people: list[str]) -> str | None:
    if not people:
        return None
    credits = _credits(title)
    compact_credits = {_compact(n): n for n in credits}
    for person in people:
        key = _compact(person)
        if key in compact_credits:
            return compact_credits[key]
        for name in credits:
            if name == person or _compact(name) == key:
                return name
    return None


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


STOPWORDS = {
    "give", "me", "a", "an", "the", "and", "or", "of", "in", "on", "to", "for",
    "with", "from", "after", "before", "since", "under", "over", "about", "around",
    "released", "release", "year", "years", "min", "mins", "minute", "minutes",
    "hour", "hours", "movie", "movies", "film", "films", "series", "show", "shows",
    "watch", "want", "please", "find", "looking", "non", "english", "imdb",
    "rating", "rated", "horror", "thriller", "drama", "comedy", "action", "crime",
}


def _fuzzy_title(query: str, title: Title) -> float:
    raw = (query or "").strip().lower()
    if len(raw) < 3:
        return 0.0
    names = [title.title, re.sub(r"\s*\(\d{4}\)\s*", " ", title.title)]
    qn = _compact(raw)
    best = 0.0
    title_query = len([t for t in TOKEN.findall(raw) if t not in STOPWORDS and not t.isdigit()]) <= 4
    for name in names:
        nn = _compact(name)
        if not qn or not nn:
            continue
        if qn == nn:
            return 1.0
        shorter, longer = (qn, nn) if len(qn) <= len(nn) else (nn, qn)
        if title_query and len(shorter) >= 4 and not shorter.isdigit() and shorter in longer:
            best = max(best, 0.94)
        best = max(best, SequenceMatcher(None, qn, nn).ratio() if title_query or len(qn) <= 24 else 0.0)
        if title_query:
            best = max(best, SequenceMatcher(None, raw, name.lower()).ratio())
        if not title_query:
            continue
        for q_tok in TOKEN.findall(raw):
            if q_tok in STOPWORDS or q_tok.isdigit() or len(q_tok) < 4:
                continue
            for n_tok in TOKEN.findall(name.lower()):
                if len(n_tok) < 3:
                    continue
                if q_tok == n_tok:
                    best = max(best, 0.96)
                elif len(q_tok) >= 5 and len(n_tok) >= 5 and (q_tok in n_tok or n_tok in q_tok):
                    best = max(best, 0.9)
                elif abs(len(q_tok) - len(n_tok)) <= 3:
                    best = max(best, SequenceMatcher(None, q_tok, n_tok).ratio() * 0.98)
    return min(best, 1.0)


def _semantic_why(title: Title, q: ParsedQuery) -> str:
    hay = " ".join([title.overview, " ".join(title.themes), " ".join(title.genres)]).lower()
    needles = [w for w in TOKEN.findall((q.semantic_text or q.raw).lower()) if len(w) > 3]
    hit = [w for w in needles if w in hay]
    theme_hit = [t for t in title.themes if t.lower() in (q.raw.lower() + " " + hay)]
    bits = []
    if theme_hit:
        bits.append("themes: " + ", ".join(theme_hit[:3]))
    if hit:
        bits.append("echoes “" + ", ".join(dict.fromkeys(hit[:4])) + "”")
    if not bits:
        bits.append(title.overview.split(".")[0][:140])
    return "; ".join(bits)


def _document(title: Title) -> str:
    return " ".join(
        [
            title.title,
            title.overview,
            " ".join(title.genres),
            " ".join(title.themes),
            " ".join(title.languages),
            " ".join(title.countries),
            " ".join(title.directors),
            " ".join(title.cast),
            " ".join(title.tags),
            title.remake_of or "",
            title.type,
        ]
    )


def _fit(docs: list[str]) -> dict:
    tokenized = [TOKEN.findall(d.lower()) for d in docs]
    df: Counter[str] = Counter()
    tfs: list[Counter[str]] = []
    for tokens in tokenized:
        counts = Counter(tokens)
        tfs.append(counts)
        df.update(counts.keys())
    n = max(len(docs), 1)
    idf = {term: math.log((n + 1) / (df[term] + 1)) + 1 for term in df}
    vectors = []
    for tf in tfs:
        vec = {term: (count / max(sum(tf.values()), 1)) * idf[term] for term, count in tf.items()}
        vectors.append(vec)
    return {"idf": idf, "docs": vectors}


def _vectorize(text: str, model: dict) -> dict[str, float]:
    tf = Counter(TOKEN.findall(text.lower()))
    total = max(sum(tf.values()), 1)
    idf: dict[str, float] = model["idf"]
    return {term: (count / total) * idf[term] for term, count in tf.items() if term in idf}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(x * x for x in a.values()))
    nb = math.sqrt(sum(x * x for x in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
