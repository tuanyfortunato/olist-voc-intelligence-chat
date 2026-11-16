import numpy as np
import pandas as pd
import pytest

from src.rag.retriever import Candidate, query_candidates, retrieve, select_reviews
from src.rag.schemas import RetrievedReview


def cand(review_id, sim, vec, text="Comentário com texto suficiente"):
    review = RetrievedReview(
        review_id=review_id,
        rating=1,
        category="bebes",
        delivery="no_prazo",
        review_date="2018-03-10",
        original_text=text,
        similarity=sim,
    )
    return Candidate(review=review, embedding=vec)


def test_select_reviews_drops_below_threshold():
    cands = [cand("a", 0.8, [1, 0, 0]), cand("b", 0.2, [0, 1, 0])]
    result = select_reviews(cands, [1, 0, 0], min_similarity=0.5, top_k=5, lambda_mult=0.5)
    assert [r.review_id for r in result] == ["a"]


def test_select_reviews_respects_top_k():
    cands = [cand(str(i), 0.9, [1, i / 10, 0]) for i in range(10)]
    assert len(select_reviews(cands, [1, 0, 0], 0.0, top_k=3, lambda_mult=0.5)) == 3


def test_select_reviews_prefers_diverse_over_duplicate():
    # A pergunta fica entre "a" e "b"; depois de escolher "a", a cópia de "a" não
    # acrescenta nada, e o MMR prefere "b", mesmo com similaridade menor
    query = [1, 0.2, 0]
    cands = [
        cand("a", 0.98, [1, 0, 0]),
        cand("a_copia", 0.98, [1, 0, 0]),
        cand("b", 0.75, [0.6, 0.8, 0]),
    ]
    ids = [r.review_id for r in select_reviews(cands, query, 0.0, top_k=2, lambda_mult=0.5)]
    assert ids[0] in {"a", "a_copia"} and "b" in ids


def test_select_reviews_empty():
    assert select_reviews([], [1, 0, 0], 0.5, 5, 0.5) == []


def test_select_reviews_min_chars():
    cands = [
        cand("curto", 0.9, [1, 0, 0], text="ok"),
        cand("longo", 0.8, [0, 1, 0], text="Chegou quebrado"),
    ]
    result = select_reviews(cands, [1, 0, 0], 0.0, 5, 0.5, min_chars=5)
    assert [r.review_id for r in result] == ["longo"]


def load(pg_conn, rows):
    from src.vector_db import load_reviews

    frame = pd.DataFrame(
        [
            {
                "review_id": review_id,
                "embedding": np.array(vector, dtype=np.float32),
                "embedding_text": text,
                "original_text": text,
                "rating": rating,
                "review_date": "2018-03-10",
                "category": "bebes",
                "delivery": "no_prazo",
                "order_id": f"o_{review_id}",
                "text_length": len(text),
            }
            for review_id, vector, text, rating in rows
        ]
    )
    load_reviews(pg_conn, frame)


ROWS = [
    ("r1", [1.0, 0.0, 0.0], "Veio quebrado", 1),
    ("r2", [0.0, 1.0, 0.0], "Chegou antes do prazo", 5),
    ("r3", [0.9, 0.1, 0.0], "Parou de funcionar", 1),
]


def test_query_candidates_returns_nearest_with_similarity_and_vector(pg_conn):
    load(pg_conn, ROWS)
    found = query_candidates(pg_conn, [1.0, 0.0, 0.0], n=2)
    assert [c.review.review_id for c in found] == ["r1", "r3"]
    assert found[0].review.similarity == pytest.approx(1.0, abs=1e-6)
    assert found[0].review.original_text == "Veio quebrado"
    assert list(found[0].embedding) == pytest.approx([1.0, 0.0, 0.0])


def test_retrieve_applies_threshold_and_top_k(pg_conn, settings):
    from dataclasses import replace

    load(pg_conn, ROWS)
    result = retrieve(pg_conn, [1.0, 0.0, 0.0], replace(settings, min_similarity=0.5, top_k=5))
    assert {r.review_id for r in result} == {"r1", "r3"}


def test_build_filter_sql_without_filters():
    from src.rag.retriever import build_filter_sql
    from src.rag.schemas import SearchFilters

    assert build_filter_sql(None) == ("", {})
    assert build_filter_sql(SearchFilters()) == ("", {})


def test_build_filter_sql_single_filters():
    from src.rag.retriever import build_filter_sql
    from src.rag.schemas import SearchFilters

    assert build_filter_sql(SearchFilters(ratings=[1, 2])) == (
        "WHERE rating = ANY(%(ratings)s)",
        {"ratings": [1, 2]},
    )
    assert build_filter_sql(SearchFilters(category="cama_mesa_banho")) == (
        "WHERE category = %(category)s",
        {"category": "cama_mesa_banho"},
    )
    assert build_filter_sql(SearchFilters(delivery="atrasada")) == (
        "WHERE delivery = ANY(%(deliveries)s)",
        {"deliveries": ["atrasada"]},
    )


def test_build_filter_sql_problem_deliveries():
    from src.rag.retriever import build_filter_sql
    from src.rag.schemas import SearchFilters

    _, params = build_filter_sql(SearchFilters(delivery="com_problema"))
    assert params == {"deliveries": ["atrasada", "nao_entregue"]}


def test_build_filter_sql_combined():
    from src.rag.retriever import build_filter_sql
    from src.rag.schemas import SearchFilters

    clause, params = build_filter_sql(SearchFilters(ratings=[5], category="moveis_decoracao"))
    assert clause == "WHERE rating = ANY(%(ratings)s) AND category = %(category)s"
    assert params == {"ratings": [5], "category": "moveis_decoracao"}


def load_with_metadata(pg_conn, rows):
    from src.vector_db import load_reviews

    frame = pd.DataFrame(
        [
            {
                "review_id": review_id,
                "embedding": np.array(vector, dtype=np.float32),
                "embedding_text": review_id,
                "original_text": review_id,
                "rating": rating,
                "review_date": "2018-03-10",
                "category": category,
                "delivery": delivery,
                "order_id": f"o_{review_id}",
                "text_length": 2,
            }
            for review_id, vector, rating, category, delivery in rows
        ]
    )
    load_reviews(pg_conn, frame)


def test_query_candidates_applies_filters(pg_conn):
    from src.rag.schemas import SearchFilters

    load_with_metadata(
        pg_conn,
        [
            ("perto_bebes", [1.0, 0.0, 0.0], 1, "bebes", "atrasada"),
            ("perto_moveis", [0.99, 0.1, 0.0], 5, "moveis", "no_prazo"),
            ("longe_moveis", [0.0, 1.0, 0.0], 5, "moveis", "nao_entregue"),
            ("mista", [0.98, 0.0, 0.1], 1, "mista", "desconhecido"),
        ],
    )
    by_category = query_candidates(pg_conn, [1.0, 0.0, 0.0], 10, SearchFilters(category="moveis"))
    assert [c.review.review_id for c in by_category] == ["perto_moveis", "longe_moveis"]

    by_rating = query_candidates(pg_conn, [1.0, 0.0, 0.0], 10, SearchFilters(ratings=[1]))
    assert {c.review.review_id for c in by_rating} == {"perto_bebes", "mista"}

    problems = query_candidates(
        pg_conn, [1.0, 0.0, 0.0], 10, SearchFilters(delivery="com_problema")
    )
    assert {c.review.review_id for c in problems} == {"perto_bebes", "longe_moveis"}
