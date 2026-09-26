from app import ai_intent
from app.catalog import load_catalog
from app.search import SemanticIndex


def test_recall_falls_back_to_embeddings_when_ai_disabled(monkeypatch):
    monkeypatch.setattr(ai_intent, "ai_enabled", lambda: False)
    titles = load_catalog()
    index = SemanticIndex(titles)

    hits, ai_used = ai_intent.recall_scene(
        "a family drama about a missing daughter", titles, index, limit=5
    )

    assert ai_used is False
    assert isinstance(hits, list)
    for h in hits:
        assert h["id"] in {t.id for t in titles}
        assert 0 <= h["confidence"] <= 100
        assert h["why"]


def test_recall_empty_query_returns_nothing(monkeypatch):
    monkeypatch.setattr(ai_intent, "ai_enabled", lambda: True)
    titles = load_catalog()
    index = SemanticIndex(titles)

    hits, ai_used = ai_intent.recall_scene("   ", titles, index, limit=5)

    assert hits == []
    assert ai_used is False


def test_recall_grounds_ids_and_clamps_confidence(monkeypatch):
    titles = load_catalog()
    index = SemanticIndex(titles)
    real_id = titles[0].id

    def fake_chat(system, user, max_tokens, timeout=12):
        return {
            "matches": [
                {"id": real_id, "confidence": 999, "why": "  "},
                {"id": "not-a-real-id", "confidence": 80, "why": "hallucinated"},
                {"id": "also-fake", "confidence": -20},
            ]
        }

    monkeypatch.setattr(ai_intent, "ai_enabled", lambda: True)
    monkeypatch.setattr(ai_intent, "_chat", fake_chat)

    hits, ai_used = ai_intent.recall_scene("some vague scene memory", titles, index, limit=5)

    assert ai_used is True
    assert len(hits) == 1
    assert hits[0]["id"] == real_id
    assert hits[0]["confidence"] == 100
    assert hits[0]["why"]


def test_recall_honors_honest_empty_ai_answer(monkeypatch):
    titles = load_catalog()
    index = SemanticIndex(titles)

    monkeypatch.setattr(ai_intent, "ai_enabled", lambda: True)
    monkeypatch.setattr(ai_intent, "_chat", lambda *a, **k: {"matches": []})

    hits, ai_used = ai_intent.recall_scene("nothing like this exists", titles, index, limit=5)

    assert hits == []
    assert ai_used is True


def test_recall_falls_back_when_ai_call_technically_fails(monkeypatch):
    titles = load_catalog()
    index = SemanticIndex(titles)

    monkeypatch.setattr(ai_intent, "ai_enabled", lambda: True)
    monkeypatch.setattr(ai_intent, "_chat", lambda *a, **k: None)

    hits, ai_used = ai_intent.recall_scene("a heist that goes wrong", titles, index, limit=5)

    assert ai_used is False
    for h in hits:
        assert h["id"] in {t.id for t in titles}
