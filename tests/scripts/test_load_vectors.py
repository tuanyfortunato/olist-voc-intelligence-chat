"""Teste da carga no banco. Precisa de TEST_DATABASE_URL, como os testes de vector_db."""

import os
import uuid

import psycopg
import pytest

from src.config import Settings
from src.knowledge_base.embedding_store import ParquetEmbeddingStore
from src.vector_store import IndexManifest, IndexMismatchError, write_manifest

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="sem TEST_DATABASE_URL")

SETTINGS = Settings(embedding_dimensions=3)


@pytest.fixture
def conn():
    schema = f"teste_{uuid.uuid4().hex[:8]}"
    connection = psycopg.connect(TEST_DATABASE_URL)
    connection.execute(f"CREATE SCHEMA {schema}")
    connection.execute(f"SET search_path TO {schema}, public")
    connection.commit()
    yield connection
    connection.rollback()
    connection.execute(f"DROP SCHEMA {schema} CASCADE")
    connection.commit()
    connection.close()


def write_index(index_dir, count_in_manifest):
    store = ParquetEmbeddingStore(index_dir)
    store.add(
        ids=["r1", "r2"],
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        documents=["Veio quebrado", "Chegou antes do prazo"],
        metadatas=[
            {
                "review_id": review_id,
                "order_id": f"o_{review_id}",
                "rating": rating,
                "review_date": "2018-03-10",
                "category": "bebes",
                "delivery": "no_prazo",
                "original_text": text,
                "text_length": len(text),
            }
            for review_id, rating, text in [
                ("r1", 1, "Veio quebrado"),
                ("r2", 5, "Chegou antes do prazo"),
            ]
        ],
    )
    store.write_final(index_dir / "embeddings.parquet")
    manifest = IndexManifest(
        SETTINGS.embedding_model_id,
        3,
        "cosine",
        "2026-11-16T10:00:00Z",
        count_in_manifest,
        ["bebes"],
    )
    write_manifest(index_dir, manifest)
    return manifest


def test_load_vectors_fills_database_and_manifest(conn, tmp_path):
    from scripts.load_vectors import load_vectors
    from src.vector_db import count_reviews, read_manifest_row

    manifest = write_index(tmp_path, count_in_manifest=2)

    assert load_vectors(conn, tmp_path, SETTINGS) == manifest
    assert count_reviews(conn) == 2
    assert read_manifest_row(conn) == manifest


def test_load_vectors_rejects_count_mismatch(conn, tmp_path):
    from scripts.load_vectors import load_vectors

    write_index(tmp_path, count_in_manifest=5)
    with pytest.raises(IndexMismatchError):
        load_vectors(conn, tmp_path, SETTINGS)
