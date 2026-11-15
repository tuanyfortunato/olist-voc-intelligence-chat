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
