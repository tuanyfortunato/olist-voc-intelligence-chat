import pytest

from src.knowledge_base.embedding_store import ParquetEmbeddingStore, read_embeddings


def metadata(review_id, rating=5):
    return {
        "review_id": review_id,
        "order_id": f"o_{review_id}",
        "rating": rating,
        "review_date": "2018-03-10",
        "category": "cama_mesa_banho",
        "delivery": "no_prazo",
        "original_text": f"Texto {review_id} 👍",
        "text_length": 9,
    }


def add(store, ids):
    store.add(
        ids=ids,
        embeddings=[[0.1, 0.2, 0.3] for _ in ids],
        documents=[f"Texto {i} aprovado" for i in ids],
        metadatas=[metadata(i) for i in ids],
    )


def test_empty_store_has_no_ids(tmp_path):
    assert ParquetEmbeddingStore(tmp_path).existing_ids() == set()


def test_existing_ids_reads_all_parts(tmp_path):
    store = ParquetEmbeddingStore(tmp_path)
    add(store, ["r1", "r2"])
    add(store, ["r3"])
    assert ParquetEmbeddingStore(tmp_path).existing_ids() == {"r1", "r2", "r3"}


def test_write_final_joins_parts_without_duplicates(tmp_path):
    store = ParquetEmbeddingStore(tmp_path)
    add(store, ["r1", "r2"])
    add(store, ["r2", "r3"])
    final = tmp_path / "embeddings.parquet"

    assert store.write_final(final) == 3

    frame = read_embeddings(final)
    assert sorted(frame["review_id"]) == ["r1", "r2", "r3"]
    row = frame.set_index("review_id").loc["r1"]
    assert list(row["embedding"]) == pytest.approx([0.1, 0.2, 0.3])
    assert row["embedding_text"] == "Texto r1 aprovado"
    assert row["original_text"] == "Texto r1 👍"
    assert row["rating"] == 5
