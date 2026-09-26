"""Optional sentence embeddings and spaCy NER. Soft-fail if models can't load."""

from __future__ import annotations

import re
from functools import lru_cache

_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_SPACY_MODEL_NAME = "en_core_web_sm"


@lru_cache(maxsize=1)
def get_embedder():
    from sentence_transformers import SentenceTransformer

    # Cached weights only. Hugging Face HEAD checks hang behind intercepting SSL.
    return SentenceTransformer(_EMBED_MODEL_NAME, local_files_only=True)


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
    """PERSON spans from spaCy NER."""
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
