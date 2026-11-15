"""Busca dos comentários (camada 2 de proteção).

A ordem é: buscar no PostgreSQL cerca de 40 candidatos com a similaridade de
cada um, descartar os que ficam abaixo do score mínimo e aplicar o MMR sobre os
que sobraram, para chegar a 10 a 15 comentários que não repitam a mesma coisa.
O corte vem antes do MMR porque é a similaridade com a pergunta que decide se
um comentário tem relação com o tema; o MMR só escolhe entre os que têm.
"""

import logging
import time
from dataclasses import dataclass

import numpy as np
from langchain_core.vectorstores.utils import maximal_marginal_relevance

from src.config import Settings
from src.rag.schemas import RetrievedReview
from src.vector_store import distance_to_similarity

logger = logging.getLogger(__name__)

# Quantos vizinhos o índice HNSW examina por busca. O padrão do pgvector é 40,
# o mesmo número de candidatos pedidos; com folga, o índice não devolve menos
# resultados do que o pedido.
EF_SEARCH = 100


@dataclass(frozen=True)
class Candidate:
    review: RetrievedReview
    embedding: list[float]


def _to_candidate(row) -> Candidate:
    review_id, rating, category, delivery, review_date, original_text, embedding, distance = row
    review = RetrievedReview(
        review_id=review_id,
        rating=rating,
        category=category,
        delivery=delivery,
        review_date=review_date,
        original_text=original_text,
        similarity=distance_to_similarity(float(distance)),
    )
    return Candidate(review=review, embedding=list(embedding))


def query_candidates(conn, query_embedding: list[float], n: int) -> list[Candidate]:
    """Os n comentários mais próximos da pergunta, com a similaridade e o vetor de cada um."""
    vector = np.asarray(query_embedding, dtype=np.float32)
    with conn.transaction():
        conn.execute(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}")
        rows = conn.execute(
            """
            SELECT review_id, rating, category, delivery, review_date, original_text,
                   embedding, embedding <=> %(vector)s AS distance
            FROM reviews
            ORDER BY embedding <=> %(vector)s
            LIMIT %(n)s
            """,
            {"vector": vector, "n": n},
        ).fetchall()
    return [_to_candidate(row) for row in rows]


def select_reviews(
    candidates: list[Candidate],
    query_embedding: list[float],
    min_similarity: float,
    top_k: int,
    lambda_mult: float,
    min_chars: int = 0,
) -> list[RetrievedReview]:
    """Corta pelo score mínimo e pelo tamanho do comentário e aplica o MMR, nessa ordem."""
    kept = [
        c
        for c in candidates
        if c.review.similarity >= min_similarity and len(c.review.original_text) >= min_chars
    ]
    if not kept:
        return []
    order = maximal_marginal_relevance(
        np.asarray(query_embedding, dtype=np.float32),
        [c.embedding for c in kept],
        lambda_mult=lambda_mult,
        k=min(top_k, len(kept)),
    )
    return [kept[i].review for i in order]


def retrieve(conn, query_embedding: list[float], settings: Settings) -> list[RetrievedReview]:
    start = time.monotonic()
    candidates = query_candidates(conn, query_embedding, settings.candidates_k)
    search_ms = (time.monotonic() - start) * 1000
    selected = select_reviews(
        candidates,
        query_embedding,
        min_similarity=settings.min_similarity,
        top_k=settings.top_k,
        lambda_mult=settings.mmr_lambda,
        min_chars=settings.min_comment_chars,
    )
    above = sum(c.review.similarity >= settings.min_similarity for c in candidates)
    logger.info(
        "etapa=recuperacao candidatos=%d acima_do_minimo=%d selecionados=%d busca_ms=%.0f",
        len(candidates),
        above,
        len(selected),
        search_ms,
    )
    return selected
