"""Avaliação das perguntas de teste pelo pipeline completo.

Roda as perguntas escolhidas pelo mesmo pipeline que a API usa, sem passar
pela API, e grava um CSV com a pergunta, a resposta, a situação, as avaliações
citadas e as recuperadas, mais cinco colunas vazias para o preenchimento manual.
Perguntas com várias mensagens, como a 12, rodam uma linha por mensagem; a
mensagem de continuação recebe como histórico a pergunta e a resposta da
pergunta indicada em history_from, rodada antes na mesma execução.

Roda numa tarefa avulsa do ECS, porque precisa do banco, e grava o CSV em
results/ no bucket do índice:
    python -m scripts.run_evaluation --ids 1,2,3,7
"""

import argparse
import csv
import json
import logging
import os
import time
from pathlib import Path

import boto3

from scripts.questions import TestQuestion, load_questions
from src.config import get_settings
from src.logging_config import setup_logging
from src.rag.pipeline import build_pipeline
from src.rag.schemas import ConversationTurn, SearchFilters

logger = logging.getLogger(__name__)

RESULTS_KEY = "results/avaliacao.csv"

# Preenchidas à mão depois da execução
MANUAL_COLUMNS = [
    "comportamento_esperado",
    "relevantes",
    "fidelidade",
    "citacoes_corretas",
    "observacao",
]


def parse_ids(raw: str) -> list[int] | None:
    raw = raw.strip()
    return [int(part) for part in raw.split(",")] if raw else None


def evaluation_rows(
    questions: list[TestQuestion], pipeline, compare_without_filters: bool = False
) -> list[dict]:
    """Uma linha por mensagem. Com compare_without_filters, as perguntas com filtro
    rodam também sem ele, na linha seguinte, para a comparação."""
    rows = []
    answers: dict[int, tuple[str, str]] = {}
    for question in questions:
        turns = question.turns or [question.question]
        filters = SearchFilters(**question.filters) if question.filters else None
        for turn_number, text in enumerate(turns, start=1):
            history = []
            if turn_number > 1 and question.history_from in answers:
                history = [ConversationTurn(*answers[question.history_from])]
            rows.append(_run_turn(question, text, turn_number, history, filters, pipeline))
            if filters and compare_without_filters:
                rows.append(_run_turn(question, text, turn_number, history, None, pipeline))
        answers[question.id] = (question.question, rows[-1]["answer"])
    return rows


def _run_turn(
    question: TestQuestion,
    text: str,
    turn: int,
    history: list[ConversationTurn],
    filters: SearchFilters | None,
    pipeline,
) -> dict:
    start = time.monotonic()
    result = pipeline.ask(text, history, filters)
    latency_ms = (time.monotonic() - start) * 1000
    cited_numbers = {review.number for review in result.cited}
    retrieved = sorted(result.cited + result.uncited, key=lambda review: review.number)
    logger.info(
        "etapa=avaliacao pergunta=%d mensagem=%d situacao=%s citadas=%d recuperadas=%d ms=%.0f",
        question.id,
        turn,
        result.status,
        len(result.cited),
        len(retrieved),
        latency_ms,
    )
    row = {
        "question_id": question.id,
        "turn": turn,
        "question": text,
        "filters": json.dumps(question.filters) if filters else "sem filtro",
        "type": question.type,
        "expected": question.expected,
        "status": result.status,
        "search_topic": result.search_topic,
        "answer": result.answer,
        "cited_ids": " ".join(review.review_id for review in result.cited),
        "retrieved_json": json.dumps(
            [
                {
                    "number": review.number,
                    "review_id": review.review_id,
                    "rating": review.rating,
                    "similarity": round(review.similarity, 4),
                    "cited": review.number in cited_numbers,
                    "original_text": review.original_text,
                }
                for review in retrieved
            ],
            ensure_ascii=False,
        ),
        "latency_ms": round(latency_ms),
    }
    row.update({column: "" for column in MANUAL_COLUMNS})
    return row


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ids", default="", help="perguntas separadas por vírgula; vazio roda todas"
    )
    parser.add_argument(
        "--without-filters",
        action="store_true",
        help="roda também sem filtro as perguntas que têm filtro, para comparar",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    setup_logging(settings.log_level)
    questions = load_questions(ids=parse_ids(args.ids))
    rows = evaluation_rows(questions, build_pipeline(settings), args.without_filters)

    path = Path("/tmp/avaliacao.csv")
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    s3 = boto3.client("s3", region_name=settings.aws_region)
    s3.upload_file(str(path), os.environ["INDEX_BUCKET"], RESULTS_KEY)


if __name__ == "__main__":
    main()
