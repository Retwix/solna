#!/usr/bin/env python3
"""Tune MATCH_SIMILARITY_THRESHOLD on your own labelled photos.

It embeds a small labelled dataset via the running face service, then sweeps
similarity thresholds and reports precision / recall / F1 at each — so you can
pick a cutoff from real data instead of guessing.

DATASET LAYOUT  (a folder you assemble by hand):

    tuning/
      alice/
        selfie.jpg          # one clear selfie of alice
        matches/            # photos that genuinely contain alice
          IMG_001.jpg
          IMG_014.jpg
      bob/
        selfie.jpg
        matches/
          IMG_003.jpg

The candidate pool is every photo under */matches/. For alice's selfie, the
true positives are alice/matches/*; every other person's photos are negatives.
So you want a handful of people, each with a selfie and the photos they're in.

PREREQS: the stack is up with real recognition:
    FACE_ENGINE=insightface  (in .env)  →  docker compose up

USAGE:
    python3 scripts/tune_threshold.py ./tuning
    FACE_SERVICE_URL=http://localhost:9200 python3 scripts/tune_threshold.py ./tuning
"""
import os
import sys
from pathlib import Path

import numpy as np
import requests

FACE_SERVICE_URL = os.getenv("FACE_SERVICE_URL", "http://localhost:9200")
IMG_EXT = {".jpg", ".jpeg", ".png"}


def embed(path: Path) -> list[np.ndarray]:
    with open(path, "rb") as fh:
        r = requests.post(
            f"{FACE_SERVICE_URL.rstrip('/')}/embed",
            files={"file": (path.name, fh, "application/octet-stream")},
            timeout=120,
        )
    r.raise_for_status()
    return [np.asarray(f["embedding"], dtype=np.float32) for f in r.json().get("faces", [])]


def normed(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n else v


def best_sim(query: np.ndarray, faces: list[np.ndarray]) -> float:
    if not faces:
        return -1.0
    q = normed(query)
    return max(float(np.dot(q, normed(f))) for f in faces)


def load_dataset(root: Path):
    people = {}
    for person_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        selfie = next((person_dir / n for n in ("selfie.jpg", "selfie.jpeg", "selfie.png")
                       if (person_dir / n).exists()), None)
        matches_dir = person_dir / "matches"
        if not selfie or not matches_dir.is_dir():
            print(f"  ! skipping {person_dir.name}: need selfie.* and matches/")
            continue
        match_files = [f for f in matches_dir.iterdir() if f.suffix.lower() in IMG_EXT]
        people[person_dir.name] = {"selfie": selfie, "matches": match_files}
    return people


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"Dataset folder not found: {root}")
        sys.exit(1)

    print(f"Face service: {FACE_SERVICE_URL}")
    people = load_dataset(root)
    if not people:
        print("No usable people found. See the layout in this script's docstring.")
        sys.exit(1)

    # Build the candidate pool: every match photo, labelled by owner, embedded once.
    print("Embedding photos…")
    pool = []  # (owner, name, faces)
    for owner, data in people.items():
        for f in data["matches"]:
            pool.append((owner, f.name, embed(f)))
    print(f"  {len(pool)} candidate photos across {len(people)} people")

    print("Embedding selfies…")
    selfies = {}
    for owner, data in people.items():
        faces = embed(data["selfie"])
        if not faces:
            print(f"  ! no face in {owner}'s selfie — excluded")
            continue
        selfies[owner] = max(faces, key=lambda v: float(np.linalg.norm(v)))  # any face; usually one

    # Precompute best similarity of each selfie to each candidate photo.
    sims = {}  # (selfie_owner, idx) -> sim
    for s_owner, q in selfies.items():
        for idx, (_, _, faces) in enumerate(pool):
            sims[(s_owner, idx)] = best_sim(q, faces)

    print("\nthreshold  precision  recall     F1     (TP/FP/FN)")
    print("-" * 55)
    best = None
    for t in [round(x, 2) for x in np.arange(0.15, 0.66, 0.05)]:
        tp = fp = fn = 0
        for s_owner in selfies:
            for idx, (owner, _, _) in enumerate(pool):
                predicted = sims[(s_owner, idx)] >= t
                actual = owner == s_owner
                if predicted and actual:
                    tp += 1
                elif predicted and not actual:
                    fp += 1
                elif not predicted and actual:
                    fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        print(f"  {t:.2f}      {precision:6.2%}    {recall:6.2%}   {f1:6.2%}   ({tp}/{fp}/{fn})")
        if best is None or f1 > best[1]:
            best = (t, f1)

    print("-" * 55)
    print(f"\nBest F1 at threshold ≈ {best[0]:.2f}  (F1 {best[1]:.2%})")
    print("Set MATCH_SIMILARITY_THRESHOLD in .env, then recreate api:  "
          "docker compose up -d --force-recreate api")
    print("Tip: if false positives hurt more than misses for your use case, "
          "pick a higher threshold than max-F1.")


if __name__ == "__main__":
    main()
