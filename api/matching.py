"""Face matching math — pure, dependency-light, DB-agnostic.

V1 matches a selfie embedding against an event's stored face embeddings using
cosine similarity in Python. At event scale (hundreds–thousands of faces) this
is plenty fast. Embeddings are expected to be L2-normalized (InsightFace's
`normed_embedding`), so cosine similarity is just a dot product.

Similarity is in [-1, 1]; higher = more alike. A guest's photo is "matched" when
its best face similarity meets the configured threshold.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np


def to_vector(embedding) -> np.ndarray:
    """Accept a JSON string or a list/array; return a float32 numpy vector."""
    if isinstance(embedding, str):
        embedding = json.loads(embedding)
    return np.asarray(embedding, dtype=np.float32)


def normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(normalize(a), normalize(b)))


@dataclass
class FaceRecord:
    photo_id: str
    embedding: np.ndarray


@dataclass
class PhotoMatch:
    photo_id: str
    similarity: float  # best face similarity for this photo


def match_faces(
    query_embedding,
    faces: list[FaceRecord],
    threshold: float,
) -> list[PhotoMatch]:
    """Return photos whose best face meets `threshold`, sorted best-first.

    Each photo appears once, scored by its single best-matching face.
    """
    q = normalize(to_vector(query_embedding))
    best: dict[str, float] = {}
    for f in faces:
        sim = float(np.dot(q, normalize(f.embedding)))
        if sim > best.get(f.photo_id, -1.0):
            best[f.photo_id] = sim

    matches = [PhotoMatch(pid, sim) for pid, sim in best.items() if sim >= threshold]
    matches.sort(key=lambda m: m.similarity, reverse=True)
    return matches
