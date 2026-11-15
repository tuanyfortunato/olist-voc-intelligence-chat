"""Junção das tabelas da Olist e montagem dos documentos da base de conhecimento.

Cada avaliação com mensagem escrita vira um documento, identificado pelo
review_id. Os metadados (nota, data, categoria e situação da entrega) vêm das
tabelas de pedidos, itens e produtos, e nunca ficam vazios: o que falta vira
"desconhecido", porque um valor nulo quebraria os filtros da busca.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from src.knowledge_base.cleaning import (
    clean_text,
    has_letters,
    join_title_and_message,
    to_embedding_text,
)

DELIVERY_ON_TIME = "no_prazo"
DELIVERY_LATE = "atrasada"
DELIVERY_NOT_DELIVERED = "nao_entregue"
UNKNOWN = "desconhecido"
MIXED_CATEGORY = "mista"


@dataclass(frozen=True)
class ReviewDocument:
    review_id: str
    order_id: str
    rating: int
    review_date: str
    category: str
    delivery: str
    original_text: str
    embedding_text: str

    def metadata(self) -> dict[str, str | int]:
        """Metadados guardados junto com o vetor e usados nos filtros da busca."""
        return {
            "review_id": self.review_id,
            "order_id": self.order_id,
            "rating": self.rating,
            "review_date": self.review_date,
            "category": self.category,
            "delivery": self.delivery,
            "original_text": self.original_text,
            "text_length": len(self.original_text),
        }


class RawTables(NamedTuple):
    reviews: pd.DataFrame
    orders: pd.DataFrame
    items: pd.DataFrame
    products: pd.DataFrame


def load_tables(raw_dir: Path) -> RawTables:
    return RawTables(
        reviews=pd.read_csv(raw_dir / "olist_order_reviews_dataset.csv"),
        orders=pd.read_csv(raw_dir / "olist_orders_dataset.csv"),
        items=pd.read_csv(raw_dir / "olist_order_items_dataset.csv"),
        products=pd.read_csv(raw_dir / "olist_products_dataset.csv"),
    )


def delivery_by_order(orders: pd.DataFrame) -> pd.Series:
    """Situação da entrega de cada pedido, com o order_id como índice.

    Pedido sem data de entrega ao cliente é "não entregue". Os demais são
    comparados com a data estimada, com data e hora, como na exploração.
    """
    delivered = pd.to_datetime(orders["order_delivered_customer_date"])
    estimated = pd.to_datetime(orders["order_estimated_delivery_date"])
    status = pd.Series(DELIVERY_LATE, index=orders.index)
    status[delivered <= estimated] = DELIVERY_ON_TIME
    status[delivered.isna()] = DELIVERY_NOT_DELIVERED
    return pd.Series(status.values, index=orders["order_id"].values)


def categories_by_order(items: pd.DataFrame, products: pd.DataFrame) -> pd.Series:
    """Conjunto de categorias de cada pedido, com o order_id como índice."""
    merged = items.merge(products[["product_id", "product_category_name"]], on="product_id")
    merged = merged.dropna(subset=["product_category_name"])
    return merged.groupby("order_id")["product_category_name"].agg(frozenset)


def _category_for(order_ids: list[str], categories: pd.Series) -> str:
    found = set()
    for order_id in order_ids:
        found |= categories.get(order_id, frozenset())
    if not found:
        return UNKNOWN
    if len(found) > 1:
        return MIXED_CATEGORY
    return found.pop()


def _delivery_for(order_ids: list[str], deliveries: pd.Series) -> str:
    statuses = {deliveries.get(order_id, UNKNOWN) for order_id in order_ids}
    return statuses.pop() if len(statuses) == 1 else UNKNOWN


def _optional_text(value) -> str | None:
    return value if isinstance(value, str) else None


def build_documents(tables: RawTables) -> list[ReviewDocument]:
    reviews = tables.reviews
    has_message = reviews["review_comment_message"].fillna("").str.strip() != ""
    with_message = reviews[has_message]

    grouped = with_message.groupby("review_id", sort=False).agg(
        order_ids=("order_id", list),
        title=("review_comment_title", "first"),
        message=("review_comment_message", "first"),
        rating=("review_score", "first"),
        date=("review_creation_date", "first"),
    )

    categories = categories_by_order(tables.items, tables.products)
    deliveries = delivery_by_order(tables.orders)

    documents = []
    for review_id, row in grouped.iterrows():
        original_text = clean_text(join_title_and_message(_optional_text(row.title), row.message))
        embedding_text = to_embedding_text(original_text)
        if not has_letters(embedding_text):
            continue
        documents.append(
            ReviewDocument(
                review_id=str(review_id),
                order_id=str(row.order_ids[0]),
                rating=int(row.rating),
                review_date=str(row.date)[:10],
                category=_category_for(row.order_ids, categories),
                delivery=_delivery_for(row.order_ids, deliveries),
                original_text=original_text,
                embedding_text=embedding_text,
            )
        )
    return documents


def summarize(documents: list[ReviewDocument]) -> dict[str, int]:
    """Contagens usadas para conferir a base com os números da exploração."""
    summary = {
        "documents": len(documents),
        "mixed_category": sum(doc.category == MIXED_CATEGORY for doc in documents),
        "unknown_category": sum(doc.category == UNKNOWN for doc in documents),
    }
    for status in (DELIVERY_ON_TIME, DELIVERY_LATE, DELIVERY_NOT_DELIVERED, UNKNOWN):
        summary[f"delivery_{status}"] = sum(doc.delivery == status for doc in documents)
    summary["categories"] = len({doc.category for doc in documents} - {MIXED_CATEGORY, UNKNOWN})
    return summary
