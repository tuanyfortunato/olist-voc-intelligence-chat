import pandas as pd
import pytest

from src.knowledge_base.preparation import RawTables, build_documents, summarize


def review(review_id, order_id, message, score=5, title=None):
    return {
        "review_id": review_id,
        "order_id": order_id,
        "review_score": score,
        "review_comment_title": title,
        "review_comment_message": message,
        "review_creation_date": "2018-03-10 00:00:00",
    }


def order(order_id, delivered, estimated="2018-03-05 00:00:00"):
    return {
        "order_id": order_id,
        "order_delivered_customer_date": delivered,
        "order_estimated_delivery_date": estimated,
    }


@pytest.fixture
def tables():
    reviews = pd.DataFrame(
        [
            review("r_sem_mensagem", "o_prazo", None),
            review("r_espacos", "o_prazo", "   "),
            review("r_pontos", "o_prazo", "..."),
            review("r_emoji", "o_prazo", "👍"),
            review("r_titulo", "o_prazo", "Chegou antes do prazo", title="Ótimo"),
            review("r_dois_pedidos", "o_prazo", "Um item veio errado", score=2),
            review("r_dois_pedidos", "o_outra_categoria", "Um item veio errado", score=2),
            review("r_sem_itens", "o_sem_itens", "Não sei o que comprei"),
            review("r_nao_entregue", "o_nao_entregue", "Não chegou", score=1),
            review("r_atrasada", "o_atrasada", "Demorou demais", score=2),
            review("r_pedido_inexistente", "o_inexistente", "Pedido sumiu", score=1),
            review("r_categoria_nula", "o_categoria_nula", "Produto bom"),
        ]
    )
    orders = pd.DataFrame(
        [
            order("o_prazo", "2018-03-01 10:00:00"),
            order("o_outra_categoria", "2018-03-02 10:00:00"),
            order("o_sem_itens", "2018-03-01 10:00:00"),
            order("o_nao_entregue", None),
            order("o_atrasada", "2018-03-09 10:00:00"),
            order("o_categoria_nula", "2018-03-01 10:00:00"),
        ]
    )
    items = pd.DataFrame(
        [
            {"order_id": "o_prazo", "product_id": "p_cama"},
            {"order_id": "o_prazo", "product_id": "p_cama"},
            {"order_id": "o_outra_categoria", "product_id": "p_movel"},
            {"order_id": "o_nao_entregue", "product_id": "p_cama"},
            {"order_id": "o_atrasada", "product_id": "p_movel"},
            {"order_id": "o_categoria_nula", "product_id": "p_sem_categoria"},
        ]
    )
    products = pd.DataFrame(
        [
            {"product_id": "p_cama", "product_category_name": "cama_mesa_banho"},
            {"product_id": "p_movel", "product_category_name": "moveis_decoracao"},
            {"product_id": "p_sem_categoria", "product_category_name": None},
        ]
    )
    return RawTables(reviews=reviews, orders=orders, items=items, products=products)


@pytest.fixture
def docs(tables):
    return {doc.review_id: doc for doc in build_documents(tables)}


def test_selection_rules(docs):
    assert "r_sem_mensagem" not in docs
    assert "r_espacos" not in docs
    assert "r_pontos" not in docs
    assert docs["r_emoji"].original_text == "👍"
    assert docs["r_emoji"].embedding_text == "aprovado"


def test_title_joined_to_message(docs):
    assert docs["r_titulo"].original_text == "Ótimo. Chegou antes do prazo"


def test_one_document_per_review_id(tables):
    ids = [doc.review_id for doc in build_documents(tables)]
    assert len(ids) == len(set(ids))


def test_category_rules(docs):
    assert docs["r_titulo"].category == "cama_mesa_banho"
    assert docs["r_dois_pedidos"].category == "mista"
    assert docs["r_sem_itens"].category == "desconhecido"
    assert docs["r_categoria_nula"].category == "desconhecido"


def test_delivery_rules(docs):
    assert docs["r_titulo"].delivery == "no_prazo"
    assert docs["r_nao_entregue"].delivery == "nao_entregue"
    assert docs["r_atrasada"].delivery == "atrasada"
    assert docs["r_pedido_inexistente"].delivery == "desconhecido"
    assert docs["r_dois_pedidos"].delivery == "no_prazo"


def test_document_fields(docs):
    doc = docs["r_atrasada"]
    assert doc.order_id == "o_atrasada"
    assert doc.rating == 2
    assert doc.review_date == "2018-03-10"


def test_metadata_never_has_missing_values(tables):
    for doc in build_documents(tables):
        for key, value in doc.metadata().items():
            assert value is not None and value == value, key  # value == value descarta NaN
            assert isinstance(value, (str, int)), key
        assert doc.metadata()["text_length"] == len(doc.original_text)


def test_summarize_counts(tables):
    summary = summarize(build_documents(tables))
    assert summary["documents"] == 8
    assert summary["mixed_category"] == 1
    assert summary["unknown_category"] == 3
    assert summary["delivery_nao_entregue"] == 1
    assert summary["delivery_atrasada"] == 1
    assert summary["delivery_desconhecido"] == 1
    assert summary["categories"] == 2
