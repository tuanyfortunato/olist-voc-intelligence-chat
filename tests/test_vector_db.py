"""Testes do banco vetorial. Precisam de um PostgreSQL com pgvector, indicado em
TEST_DATABASE_URL; o CI cria esse banco, e no Mac os testes são pulados."""

import os
import uuid

import numpy as np
import pandas as pd
import psycopg
import pytest

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="sem TEST_DATABASE_URL")


@pytest.fixture
def conn():
    """Conexão num schema próprio, apagado no fim, para um teste não ver o outro."""
    from src.vector_db import ensure_schema

    schema = f"teste_{uuid.uuid4().hex[:8]}"
    connection = psycopg.connect(TEST_DATABASE_URL)
    connection.execute(f"CREATE SCHEMA {schema}")
    connection.execute(f"SET search_path TO {schema}, public")
    ensure_schema(connection, dimensions=3)
    yield connection
    connection.rollback()
    connection.execute(f"DROP SCHEMA {schema} CASCADE")
    connection.commit()
    connection.close()


def frame(rows):
    return pd.DataFrame(
        [
            {
                "review_id": review_id,
                "embedding": np.array(vector, dtype=np.float32),
                "embedding_text": text,
                "original_text": text,
                "rating": rating,
                "review_date": "2018-03-10",
                "category": "cama_mesa_banho",
                "delivery": "no_prazo",
                "order_id": f"o_{review_id}",
                "text_length": len(text),
            }
            for review_id, vector, text, rating in rows
        ]
    )


ROWS = [
    ("r1", [1.0, 0.0, 0.0], "Veio quebrado", 1),
    ("r2", [0.0, 1.0, 0.0], "Chegou antes do prazo", 5),
    ("r3", [0.9, 0.1, 0.0], "Parou de funcionar", 1),
]


def test_ensure_schema_is_idempotent(conn):
    from src.vector_db import ensure_schema

    ensure_schema(conn, dimensions=3)
    ensure_schema(conn, dimensions=3)


def test_load_reviews_counts_and_creates_hnsw_index(conn):
    from src.vector_db import count_reviews, load_reviews

    assert load_reviews(conn, frame(ROWS)) == 3
    assert count_reviews(conn) == 3
    indexes = conn.execute(
        "SELECT indexdef FROM pg_indexes WHERE tablename = 'reviews' AND indexdef LIKE '%hnsw%'"
    ).fetchall()
    assert len(indexes) == 1 and "vector_cosine_ops" in indexes[0][0]


def test_load_reviews_replaces_previous_content(conn):
    from src.vector_db import count_reviews, load_reviews

    load_reviews(conn, frame(ROWS))
    load_reviews(conn, frame(ROWS[:1]))
    assert count_reviews(conn) == 1


def test_loaded_vectors_support_cosine_search(conn):
    from src.vector_db import load_reviews

    load_reviews(conn, frame(ROWS))
    nearest = conn.execute(
        "SELECT review_id FROM reviews ORDER BY embedding <=> %s::vector LIMIT 2",
        ("[1, 0, 0]",),
    ).fetchall()
    assert [row[0] for row in nearest] == ["r1", "r3"]


def test_manifest_roundtrip_in_database(conn):
    from src.vector_db import read_manifest_row, write_manifest_row
    from src.vector_store import IndexManifest

    manifest = IndexManifest("cohere.embed-multilingual-v3", 3, "cosine", "x", 3, ["bebes"])
    write_manifest_row(conn, manifest)
    write_manifest_row(conn, manifest)
    assert read_manifest_row(conn) == manifest


def test_read_index_status(conn):
    from src.vector_db import load_reviews, read_index_status, write_manifest_row
    from src.vector_store import IndexManifest

    load_reviews(conn, frame(ROWS))
    manifest = IndexManifest("cohere.embed-multilingual-v3", 3, "cosine", "x", 3, ["bebes"])
    write_manifest_row(conn, manifest)
    status = read_index_status(conn)
    assert status.manifest == manifest and status.documents == 3


def test_themes_table_classification_and_rows(conn):
    from src.vector_db import (
        ensure_themes_table,
        load_reviews,
        read_review_rows,
        read_texts_to_classify,
        write_themes,
    )

    load_reviews(conn, frame(ROWS))
    ensure_themes_table(conn)
    ensure_themes_table(conn)
    assert [review_id for review_id, _ in read_texts_to_classify(conn)] == ["r1", "r2", "r3"]

    write_themes(conn, {"r1": ["avaria"], "r2": []}, "modelo")
    assert read_texts_to_classify(conn) == [("r3", "Parou de funcionar")]
    assert len(read_texts_to_classify(conn, redo=True)) == 3

    write_themes(conn, {"r1": ["avaria", "nao_volta"]}, "outro")
    rows = {row[0]: row for row in read_review_rows(conn)}
    assert rows["r1"][6] == ["avaria", "nao_volta"]
    assert rows["r2"][6] == []
    assert rows["r3"][6] == []
    assert rows["r1"][1:6] == (1, "no_prazo", "cama_mesa_banho", "2018-03-10", "Veio quebrado")
