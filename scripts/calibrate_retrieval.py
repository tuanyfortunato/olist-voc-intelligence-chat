"""Calibração da busca: os 30 comentários mais próximos de cada pergunta de teste.

Para as perguntas 1 a 11, busca os comentários com a pergunta original e com o
tema reescrito pelo Nova Micro, sem score mínimo e sem MMR, e grava o score de
cada um. A tabela sustenta a escolha do score mínimo, do top-k, do uso da
reescrita e do tratamento dos comentários curtos. Também mede o tempo de cada
busca no banco.

Roda numa tarefa avulsa do ECS, porque precisa do banco, e grava as tabelas em
results/ no bucket do índice:
    python -m scripts.calibrate_retrieval
"""

import csv
import logging
import os
import statistics
import time
from collections.abc import Callable
from pathlib import Path

import boto3

from scripts.questions import TestQuestion, load_questions
from src.aws.bedrock import embed_query, get_chat_model, get_runtime_client
from src.config import get_settings
from src.logging_config import setup_logging
from src.rag.question_analysis import AnalysisResult, analyze_question
from src.rag.retriever import Candidate, query_candidates
from src.vector_db import connect

logger = logging.getLogger(__name__)

QUESTION_IDS = list(range(1, 12))
RESULTS_PREFIX = "results"
SHORT_COMMENT_CHARS = 10
SUMMARY_RANKS = [1, 5, 10, 15, 20, 30]

SearchFunction = Callable[[list[float], int], tuple[list[Candidate], float]]


def calibration_rows(
    questions: list[TestQuestion],
    analyze: Callable[[str], AnalysisResult],
    embed: Callable[[str], list[float]],
    search: SearchFunction,
    n: int = 30,
) -> list[dict]:
    rows = []
    for question in questions:
        result = analyze(question.question)
        variants = [("original", question.question)]
        if result.analysis.kind == "in_scope":
            variants.append(("rewritten", result.analysis.search_topic))
        for variant, text in variants:
            candidates, search_ms = search(embed(text), n)
            for rank, candidate in enumerate(candidates, start=1):
                review = candidate.review
                rows.append(
                    {
                        "question_id": question.id,
                        "type": question.type,
                        "kind": result.analysis.kind,
                        "variant": variant,
                        "text_used": text,
                        "rank": rank,
                        "similarity": round(review.similarity, 4),
                        "rating": review.rating,
                        "text_length": len(review.original_text),
                        "review_id": review.review_id,
                        "original_text": review.original_text,
                        "search_ms": round(search_ms, 1),
                    }
                )
    return rows


def summarize_rows(rows: list[dict]) -> list[dict]:
    """Uma linha por pergunta e variante: o score em algumas posições e quantos
    comentários curtos aparecem entre os 15 primeiros."""
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        groups.setdefault((row["question_id"], row["variant"]), []).append(row)
    summary = []
    for (question_id, variant), group in groups.items():
        group = sorted(group, key=lambda row: row["rank"])
        line = {
            "question_id": question_id,
            "type": group[0]["type"],
            "variant": variant,
            "text_used": group[0]["text_used"],
        }
        for rank in SUMMARY_RANKS:
            line[f"top{rank}"] = group[rank - 1]["similarity"] if len(group) >= rank else None
        line["short_in_top15"] = sum(
            row["text_length"] <= SHORT_COMMENT_CHARS for row in group[:15]
        )
        line["search_ms"] = group[0]["search_ms"]
        summary.append(line)
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    client = get_runtime_client(settings)
    llm = get_chat_model(settings, settings.analysis_max_tokens)
    questions = load_questions(ids=QUESTION_IDS)

    with connect(settings) as conn:

        def search(embedding: list[float], n: int) -> tuple[list[Candidate], float]:
            start = time.monotonic()
            candidates = query_candidates(conn, embedding, n)
            return candidates, (time.monotonic() - start) * 1000

        rows = calibration_rows(
            questions,
            analyze=lambda text: analyze_question(text, [], llm),
            embed=lambda text: embed_query(client, text, settings),
            search=search,
        )

    summary = summarize_rows(rows)
    times = [line["search_ms"] for line in summary]
    logger.info(
        "etapa=calibracao buscas=%d tempo_mediano_ms=%.0f tempo_maximo_ms=%.0f",
        len(times),
        statistics.median(times),
        max(times),
    )
    for line in summary:
        logger.info("etapa=calibracao %s", " ".join(f"{k}={v}" for k, v in line.items()))

    out_dir = Path("/tmp/calibracao")
    out_dir.mkdir(exist_ok=True)
    write_csv(out_dir / "calibracao.csv", rows)
    write_csv(out_dir / "calibracao_resumo.csv", summary)
    s3 = boto3.client("s3", region_name=settings.aws_region)
    for name in ["calibracao.csv", "calibracao_resumo.csv"]:
        s3.upload_file(str(out_dir / name), os.environ["INDEX_BUCKET"], f"{RESULTS_PREFIX}/{name}")


if __name__ == "__main__":
    main()
