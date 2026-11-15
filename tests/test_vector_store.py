import pytest

from src.vector_store import (
    IndexManifest,
    IndexMismatchError,
    check_manifest,
    distance_to_similarity,
    read_manifest,
    write_manifest,
)


def manifest(**changes):
    values = {
        "embedding_model_id": "cohere.embed-multilingual-v3",
        "dimensions": 1024,
        "distance": "cosine",
        "created_at": "2026-11-16T10:00:00Z",
        "document_count": 3,
        "categories": ["moveis_decoracao"],
    }
    values.update(changes)
    return IndexManifest(**values)


def test_manifest_roundtrip(tmp_path):
    write_manifest(tmp_path, manifest())
    assert read_manifest(tmp_path) == manifest()


def test_manifest_from_dict_ignores_unknown_fields():
    data = {**manifest().__dict__, "chroma_version": "1.5.9"}
    assert IndexManifest.from_dict(data) == manifest()


def test_check_manifest_accepts_matching_index(settings):
    check_manifest(manifest(), settings, row_count=3)


def test_check_manifest_rejects_other_model(settings):
    with pytest.raises(IndexMismatchError, match="modelo"):
        check_manifest(manifest(embedding_model_id="outro"), settings, row_count=3)


def test_check_manifest_rejects_other_dimensions(settings):
    with pytest.raises(IndexMismatchError, match="dimensões"):
        check_manifest(manifest(dimensions=512), settings, row_count=3)


def test_check_manifest_rejects_count_mismatch(settings):
    with pytest.raises(IndexMismatchError, match="documentos"):
        check_manifest(manifest(), settings, row_count=2)


def test_similarity():
    assert distance_to_similarity(0.25) == 0.75
