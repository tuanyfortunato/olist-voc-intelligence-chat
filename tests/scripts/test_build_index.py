import json

import pandas as pd

from scripts import build_index


def write_tables(raw_dir):
    pd.DataFrame(
        [
            {
                "review_id": "r1",
                "order_id": "o1",
                "review_score": 1,
                "review_comment_title": None,
                "review_comment_message": "Não chegou",
                "review_creation_date": "2018-03-10 00:00:00",
            },
            {
                "review_id": "r2",
                "order_id": "o1",
                "review_score": 5,
                "review_comment_title": None,
                "review_comment_message": "...",
                "review_creation_date": "2018-03-10 00:00:00",
            },
        ]
    ).to_csv(raw_dir / "olist_order_reviews_dataset.csv", index=False)
    pd.DataFrame(
        [
            {
                "order_id": "o1",
                "order_delivered_customer_date": None,
                "order_estimated_delivery_date": "2018-03-05 00:00:00",
            }
        ]
    ).to_csv(raw_dir / "olist_orders_dataset.csv", index=False)
    pd.DataFrame([{"order_id": "o1", "product_id": "p1"}]).to_csv(
        raw_dir / "olist_order_items_dataset.csv", index=False
    )
    pd.DataFrame([{"product_id": "p1", "product_category_name": "telefonia"}]).to_csv(
        raw_dir / "olist_products_dataset.csv", index=False
    )


def test_prepare_mode_writes_summary(tmp_path):
    write_tables(tmp_path)
    summary_path = tmp_path / "prepare_summary.json"

    build_index.main(
        ["--mode", "prepare", "--raw-dir", str(tmp_path), "--summary-path", str(summary_path)]
    )

    summary = json.loads(summary_path.read_text())
    assert summary["documents"] == 1
    assert summary["delivery_nao_entregue"] == 1
    assert summary["categories"] == 1


def test_build_full_index_writes_manifest(tmp_path, settings):
    write_tables(tmp_path)
    from src.knowledge_base.preparation import build_documents, load_tables
    from src.vector_store import open_collection, read_manifest

    documents = build_documents(load_tables(tmp_path))
    index_dir = tmp_path / "index"

    manifest = build_index.build_full_index(
        documents, settings, embed=lambda texts: [[0.5] * 3 for _ in texts], index_dir=index_dir
    )

    assert manifest.document_count == 1
    assert manifest.embedding_model_id == "cohere.embed-multilingual-v3"
    assert manifest.distance == "cosine"
    assert manifest.categories == ["telefonia"]
    assert read_manifest(index_dir) == manifest
    assert open_collection(index_dir, settings.collection_name).count() == 1
