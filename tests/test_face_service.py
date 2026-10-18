"""The face service: loads its model before photos arrive. InsightFace itself is
replaced by a stand-in at the import boundary; the real model is 300 MB."""
import importlib.util
import sys
import types

import pytest
from fastapi.testclient import TestClient

from conftest import ROOT


@pytest.fixture()
def load_face_service(monkeypatch):
    """Load faceservice/app.py with the given engine and a stand-in InsightFace.
    Returns (module, models): every model the service constructs is appended."""
    models = []

    class StandInFaceAnalysis:
        def __init__(self, name, providers, allowed_modules=None):
            self.allowed_modules = allowed_modules
            models.append(self)

        def prepare(self, ctx_id, det_size):
            pass

        def get(self, bgr):
            return []

    insightface_app = types.ModuleType("insightface.app")
    insightface_app.FaceAnalysis = StandInFaceAnalysis
    monkeypatch.setitem(sys.modules, "insightface", types.ModuleType("insightface"))
    monkeypatch.setitem(sys.modules, "insightface.app", insightface_app)

    def _load(engine):
        monkeypatch.setenv("FACE_ENGINE", engine)
        spec = importlib.util.spec_from_file_location("face_service_app", ROOT / "faceservice" / "app.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, models

    return _load


@pytest.mark.parametrize(
    ("engine", "models_loaded"),
    [("insightface", 1), ("fake", 0)],
)
def test_the_model_loads_at_startup_only_for_the_real_engine(load_face_service, engine, models_loaded):
    service, models = load_face_service(engine)

    with TestClient(service.app):
        assert len(models) == models_loaded


def test_only_the_detection_and_recognition_models_are_loaded(load_face_service):
    service, models = load_face_service("insightface")

    with TestClient(service.app):
        assert models[0].allowed_modules == ["detection", "recognition"]
