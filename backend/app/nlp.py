"""Real ML layer: sentence embeddings for semantic ranking, NER for name detection.

Both are optional, cached, and fail soft — if the models can't load (no
internet on first run to fetch weights, etc.) the app falls back to the
existing TF-IDF + regex behavior. Nothing else in the request path depends on
this module being available.
"""

from __future__ import annotations

import re
from functools import lru_cache

_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_SPACY_MODEL_NAME = "en_core_web_sm"


@lru_cache(maxsize=1)
def get_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(_EMBED_MODEL_NAME)


@lru_cache(maxsize=1)
def get_nlp():
    import spacy

    nlp = spacy.load(_SPACY_MODEL_NAME, disable=["lemmatizer", "attribute_ruler"])
    return nlp


@lru_cache(maxsize=1)
def embeddings_available() -> bool:
    try:
        get_embedder()
        return True
    except Exception:  # noqa: BLE001
        return False


@lru_cache(maxsize=1)
def ner_available() -> bool:
    try:
        get_nlp()
        return True
    except Exception:  # noqa: BLE001
        return False


def encode(texts: list[str]):
    """L2-normalized sentence embeddings, one row per text."""
    model = get_embedder()
    return model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)


_TITLE_NOISE = re.compile(
    r"\b(movies?|films?|shows?|series|titles?|starring|featuring|directed|by|of|from|the|a|an)\b",
    re.I,
)


def extract_person_names(text: str) -> list[str]:
    """Pull PERSON-entity spans out of free text using spaCy NER.

    This generalizes past the old regex heuristic: it works for arbitrary
    names in arbitrary phrasing ("something with Tom Hanks", "Mammootty
    thrillers", "any Scorsese films") without a hand-maintained pattern list.
    """
    if not text.strip():
        return []
    nlp = get_nlp()
    doc = nlp(text)
    names: list[str] = []
    seen: set[str] = set()
    for ent in doc.ents:
        if ent.label_ != "PERSON":
            continue
        cleaned = _TITLE_NOISE.sub(" ", ent.text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,'\"")
        if len(cleaned) < 2:
            continue
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            names.append(cleaned)
    return names
