"""Avaliação das perguntas de teste pelo pipeline completo.

Roda as perguntas escolhidas pelo mesmo pipeline que a API usa, sem passar
pela API, e grava um CSV com a pergunta, a resposta, a situação, as avaliações
citadas e as recuperadas. As colunas do preenchimento manual entram na etapa de
avaliação.

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

logger = logging.getLogger(__name__)

RESULTS_KEY = "results/avaliacao.csv"


def parse_ids(raw: str) -> list[int] | None:
    raw = raw.strip()
    return [int(part) for part in raw.split(",")] if raw else None


def evaluation_rows(questions: list[TestQuestion], pipeline) -> list[dict]:
    rows = []
    for question in questions:
        start = time.monotonic()
        result = pipeline.ask(question.question)
        latency_ms = (time.monotonic() - start) * 1000
        cited_numbers = {review.number for review in result.cited}
        retrieved = sorted(result.cited + result.uncited, key=lambda review: review.number)
        rows.append(
            {
                "question_id": question.id,
                "question": question.question,
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
        )
        logger.info(
            "etapa=avaliacao pergunta=%d situacao=%s citadas=%d recuperadas=%d ms=%.0f",
            question.id,
            result.status,
            len(result.cited),
            len(retrieved),
            latency_ms,
        )
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ids", default="", help="perguntas separadas por vírgula; vazio roda todas"
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    setup_logging(settings.log_level)
    questions = load_questions(ids=parse_ids(args.ids))
    rows = evaluation_rows(questions, build_pipeline(settings))

    path = Path("/tmp/avaliacao.csv")
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    s3 = boto3.client("s3", region_name=settings.aws_region)
    s3.upload_file(str(path), os.environ["INDEX_BUCKET"], RESULTS_KEY)


if __name__ == "__main__":
    main()
