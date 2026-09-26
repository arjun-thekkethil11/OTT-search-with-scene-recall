from app.parser import parse_query
from app.catalog import load_catalog
from app.search import SemanticIndex, search


def test_example_query_parses_hard_filters():
    q = parse_query(
        "Give me a 90–120 min thriller, non-English, released after 2018, IMDb > 7, no horror."
    )
    assert q.runtime_min == 90
    assert q.runtime_max == 120
    assert "Thriller" in q.genres_include
    assert "Horror" in q.genres_exclude
    assert q.non_english is True
    assert q.year_min == 2019
    assert q.imdb_min is not None and q.imdb_min >= 7.0


def test_year_range_is_not_parsed_as_runtime():
    q = parse_query("French films from 2019–2023 under 2 hours")
    assert q.year_min == 2019
    assert q.year_max == 2023
    assert q.runtime_min is None
    assert q.runtime_max == 120
    assert "French" in q.languages_include


def test_example_query_returns_matching_titles():
    parsed = parse_query(
        "Give me a 90-120 min thriller, non-English, released after 2018, IMDb > 7, no horror."
    )
    catalog = load_catalog()
    index = SemanticIndex(catalog)
    hits, _ = search(catalog, parsed, index, limit=20)
    ids = {h.title.id for h in hits}
    assert "the-call" in ids
    assert "joji" in ids
    assert "badla" in ids
    assert "kill-2024" in ids
    assert "train-to-busan" not in ids
    assert "the-platform" not in ids
    assert "parasite" not in ids
    for hit in hits:
        t = hit.title
        assert t.runtime_min is None or 90 <= t.runtime_min <= 120
        assert t.year >= 2019
        assert t.imdb is not None and t.imdb > 7
        assert "Horror" not in t.genres
        assert "Thriller" in t.genres
        assert any(lang != "English" for lang in t.languages)
        assert not any(r.kind == "miss" for r in hit.reasons)


def test_drishyam_original_and_hindi_remake_are_distinct():
    catalog = {t.id: t for t in load_catalog()}
    original = catalog["drishyam-2013"]
    remake = catalog["drishyam-2015"]
    assert original.languages == ["Malayalam"]
    assert original.year == 2013
    assert "Original" in original.tags
    assert remake.languages == ["Hindi"]
    assert remake.year == 2015
    assert "Remake" in remake.tags
    assert "2013" in (remake.remake_of or "")


def test_title_typos_still_find_the_film():
    catalog = load_catalog()
    index = SemanticIndex(catalog)
    cases = [
        ("Dhrishyam", {"drishyam-2013", "drishyam-2015"}),
        ("Drishyam", {"drishyam-2013", "drishyam-2015"}),
        ("parasie", {"parasite"}),
        ("jojii", {"joji"}),
        ("squid gam", {"squid-game"}),
    ]
    for query, expected in cases:
        hits, _ = search(catalog, parse_query(query), index, limit=8)
        ids = {h.title.id for h in hits[:5]}
        assert expected <= ids, f"{query} -> {ids}"


def test_person_name_queries_rank_their_titles():
    catalog = load_catalog()
    index = SemanticIndex(catalog)
    parsed = parse_query("mohanlal movies")
    assert parsed.types == ["movie"]
    assert any("mohanlal" in p.lower() for p in parsed.people_include)
    hits, _ = search(catalog, parsed, index, limit=12)
    ids = [h.title.id for h in hits]
    assert "drishyam-2013" in ids
    assert "lucifer-2019" in ids
    assert "parasite" not in ids
    assert "fight-club" not in ids
    for hit in hits:
        assert hit.title.type == "movie"
        assert "Mohanlal" in hit.title.cast
    assert "bheeshma-parvam" not in ids

    mammootty = parse_query("mammootty movies")
    mam_hits, _ = search(catalog, mammootty, index, limit=12)
    mam_ids = {h.title.id for h in mam_hits}
    assert "bheeshma-parvam" in mam_ids
    for hit in mam_hits:
        assert "Mammootty" in hit.title.cast

    pitt = parse_query("brad pit movies")
    hits, _ = search(catalog, pitt, index, limit=12)
    pitt_ids = {h.title.id for h in hits}
    assert {"fight-club", "se7en", "moneyball"} <= pitt_ids
    for hit in hits:
        assert hit.title.type == "movie"
        assert "Brad Pitt" in hit.title.cast

    dakota = parse_query("dakota johnson movies")
    hits, _ = search(catalog, dakota, index, limit=12)
    dakota_ids = {h.title.id for h in hits}
    assert "fifty-shades" in dakota_ids or "materialists" in dakota_ids
    for hit in hits:
        assert "Dakota Johnson" in hit.title.cast


def test_dual_role_is_not_stunt_double():
    parsed = parse_query("movies in which bradpitt does double role")
    assert parsed.dual_role is True
    assert parsed.types == ["movie"]
    assert any("pitt" in p.lower().replace(" ", "") for p in parsed.people_include)
    catalog = load_catalog()
    index = SemanticIndex(catalog)
    hits, _ = search(catalog, parsed, index, limit=12)
    assert all(h.title.id != "once-upon-hollywood" for h in hits)
    assert all("Brad Pitt" in (h.title.dual_role_cast or []) for h in hits)

    shobana = parse_query("shobana double role")
    hits, _ = search(catalog, shobana, index, limit=8)
    ids = {h.title.id for h in hits}
    assert "manichitrathazhu" in ids

    hardy = parse_query("tom hardy dual role movies")
    hits, _ = search(catalog, hardy, index, limit=8)
    assert any(h.title.id == "legend-2015" for h in hits)


def test_messy_below_imdb_thriller_query():
    parsed = parse_query("triller movies that has more than below 5 imdb rating")
    assert "Thriller" in parsed.genres_include
    assert parsed.types == ["movie"]
    assert parsed.imdb_max == 5
    catalog = load_catalog()
    index = SemanticIndex(catalog)
    hits, _ = search(catalog, parsed, index, limit=20)
    for hit in hits:
        assert "Thriller" in hit.title.genres
        assert hit.title.type == "movie"
        assert hit.title.imdb is not None and hit.title.imdb <= 5
    assert all(h.title.id != "kill-2024" for h in hits)
