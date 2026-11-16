import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.vector_db import IndexStatus
from src.vector_store import IndexManifest, IndexMismatchError

from .conftest import make_limiter

MANIFEST = IndexManifest(
    "cohere.embed-multilingual-v3", 1024, "cosine", "2026-11-15T20:49:11Z", 40521, ["bebes"]
)


def test_health_reports_documents_from_database(settings):
    app = create_app(
        settings, status_provider=lambda: IndexStatus(MANIFEST, 40521), limiter=make_limiter()
    )
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "documents": 40521,
        "embedding_model": "cohere.embed-multilingual-v3",
        "index_created_at": "2026-11-15T20:49:11Z",
    }


def test_health_is_503_when_database_is_unreachable(settings):
    calls = {"n": 0}

    def provider():
        calls["n"] += 1
        if calls["n"] > 1:
            raise OSError("banco fora do ar")
        return IndexStatus(MANIFEST, 40521)

    app = create_app(settings, status_provider=provider, limiter=make_limiter())
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 503


def test_app_does_not_start_when_manifest_mismatches(settings):
    app = create_app(settings, status_provider=lambda: IndexStatus(MANIFEST, 10))
    with pytest.raises(IndexMismatchError):
        with TestClient(app):
            pass
