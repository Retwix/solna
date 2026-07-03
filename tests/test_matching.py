"""Behaviour: the face-matching math (pure, no DB)."""
from matching import FaceRecord, cosine_similarity, match_faces, to_vector


def test_identical_embeddings_are_maximally_similar():
    a = to_vector([1.0, 0.0, 0.0])
    assert cosine_similarity(a, a) == 1.0


def test_orthogonal_embeddings_are_dissimilar():
    a = to_vector([1.0, 0.0, 0.0])
    b = to_vector([0.0, 1.0, 0.0])
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_match_returns_only_photos_over_threshold_best_first():
    me = [1.0, 0.0, 0.0]
    faces = [
        FaceRecord(photo_id="p1", embedding=to_vector([1.0, 0.0, 0.0])),    # sim 1.0
        FaceRecord(photo_id="p2", embedding=to_vector([0.9, 0.1, 0.0])),    # high
        FaceRecord(photo_id="p3", embedding=to_vector([0.0, 1.0, 0.0])),    # sim ~0
    ]
    matches = match_faces(me, faces, threshold=0.35)
    ids = [m.photo_id for m in matches]
    assert ids[:2] == ["p1", "p2"]   # best first
    assert "p3" not in ids           # below threshold


def test_a_malformed_stored_embedding_is_skipped_not_fatal():
    """A face row whose embedding dimension doesn't match the query (corrupt
    or legacy data) must be skipped — one bad row must never 500 the whole
    guest match."""
    faces = [
        FaceRecord(photo_id="bad", embedding=to_vector([1.0, 0.0])),  # wrong dim
        FaceRecord(photo_id="good", embedding=to_vector([1.0, 0.0, 0.0])),
    ]
    matches = match_faces([1.0, 0.0, 0.0], faces, threshold=0.35)
    assert [m.photo_id for m in matches] == ["good"]


def test_each_photo_scored_by_its_best_face():
    me = [1.0, 0.0, 0.0]
    faces = [
        FaceRecord(photo_id="p1", embedding=to_vector([0.0, 1.0, 0.0])),   # bad
        FaceRecord(photo_id="p1", embedding=to_vector([1.0, 0.0, 0.0])),   # great
    ]
    matches = match_faces(me, faces, threshold=0.35)
    assert len(matches) == 1
    assert matches[0].photo_id == "p1"
    assert matches[0].similarity == 1.0
