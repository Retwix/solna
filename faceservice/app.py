"""Solna face service (V1).

Isolates the heavy facial-recognition dependency (InsightFace) in one small
service. Exposes a single endpoint:

    POST /embed   (multipart image)  ->  { "faces": [ {bbox, det_score, embedding[512]}, ... ] }

Both the FTP server (on photo ingest) and the API (on guest selfie) call it, so
the InsightFace model is downloaded and loaded in exactly one place.

FACE_ENGINE selects the implementation:
  * insightface  — real detection + 512-d embeddings (default)
  * fake         — deterministic pseudo-embeddings, no model download; lets the
                   whole pipeline run end-to-end for plumbing/dev without GPUs
                   or large downloads. NOT for real recognition.
"""
import hashlib
import io
import os
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile
from PIL import Image, ImageOps

FACE_ENGINE = os.getenv("FACE_ENGINE", "insightface").lower()
EMBED_DIM = 512

_model = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    if FACE_ENGINE != "fake":
        _get_model()
    yield


app = FastAPI(title="Solna Face Service", version="0.1.0", lifespan=lifespan)


def _load_image(data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    return np.asarray(img)


def _embed_fake(rgb: np.ndarray) -> list[dict]:
    """One deterministic 'face' per image, derived from pixel content.

    Same image -> same embedding (so a selfie can 'match' an identical crop),
    but it carries no real identity. Dev/plumbing only.
    """
    h = hashlib.sha256(rgb.tobytes()).digest()
    seed = int.from_bytes(h[:8], "little")
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(EMBED_DIM).astype(np.float32)
    vec /= np.linalg.norm(vec)
    H, W = rgb.shape[:2]
    return [{"bbox": [0, 0, W, H], "det_score": 1.0, "embedding": vec.tolist()}]


def _get_model():
    global _model
    if _model is None:
        from insightface.app import FaceAnalysis

        m = FaceAnalysis(name=os.getenv("INSIGHTFACE_MODEL", "buffalo_l"),
                         allowed_modules=["detection", "recognition"],
                         providers=["CPUExecutionProvider"])
        m.prepare(ctx_id=-1, det_size=(640, 640))
        _model = m
    return _model


def _embed_insightface(rgb: np.ndarray) -> list[dict]:
    model = _get_model()
    bgr = rgb[:, :, ::-1]  # InsightFace expects BGR
    out = []
    for f in model.get(bgr):
        out.append({
            "bbox": [float(x) for x in f.bbox.tolist()],
            "det_score": float(getattr(f, "det_score", 0.0)),
            "embedding": f.normed_embedding.astype(np.float32).tolist(),
        })
    return out


@app.get("/healthz")
def healthz():
    return {"status": "ok", "engine": FACE_ENGINE}


@app.post("/embed")
async def embed(file: UploadFile):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    try:
        rgb = _load_image(data)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid image")

    faces = _embed_fake(rgb) if FACE_ENGINE == "fake" else _embed_insightface(rgb)
    return {"engine": FACE_ENGINE, "faces": faces}
