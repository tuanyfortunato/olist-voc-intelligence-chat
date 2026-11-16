"""Classifica as avaliações nos temas do painel e gera os números dele.

Roda numa tarefa avulsa do ECS, disparada pelo workflow Classify themes, porque
o banco fica numa rede privada da AWS. Lê os comentários do banco, classifica
os que ainda não têm tema com o Nova Micro e grava o resultado na tabela
review_themes. Depois calcula o dashboard.json e separa uma amostra para a
revisão manual, e envia os dois para o S3, de onde o workflow os copia.

Uso, a partir da raiz do projeto, com INDEX_BUCKET e as variáveis do banco definidas:
    python -m scripts.classify_themes            # só o que falta classificar
    python -m scripts.classify_themes --redo     # classifica tudo de novo
    python -m scripts.classify_themes --skip-classification  # só refaz os números
"""

import argparse
import csv
import json
import logging
import os
import tempfile
from pathlib import Path

import boto3
from botocore.config import Config

from src.config import get_settings
from src.logging_config import setup_logging
from src.themes.classifier import ReviewText, classify_reviews, converse
from src.themes.dashboard import ReviewRow, build_dashboard, review_sample
from src.vector_db import (
    connect,
    ensure_themes_table,
    read_review_rows,
    read_texts_to_classify,
    write_themes,
)

logger = logging.getLogger(__name__)

RESULTS_PREFIX = "results/temas"
DASHBOARD_FILE = "dashboard.json"
SAMPLE_FILE = "amostra_revisao.csv"
# Preço do Nova Micro sob demanda em us-east-1, em dólares por milhão de tokens
PRICE_INPUT = 0.035
PRICE_OUTPUT = 0.14


def to_rows(records: list[tuple]) -> list[ReviewRow]:
    return [
        ReviewRow(
            review_id=review_id,
            rating=rating,
            delivery=delivery,
            category=category,
            review_date=review_date,
            original_text=text,
            themes=tuple(themes),
        )
        for review_id, rating, delivery, category, review_date, text, themes in records
    ]


def write_outputs(rows: list[ReviewRow], model_id: str, folder: Path) -> list[Path]:
    dashboard = folder / DASHBOARD_FILE
    dashboard.write_text(
        json.dumps(build_dashboard(rows, model_id), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    sample = folder / SAMPLE_FILE
    records = review_sample(rows)
    with sample.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    return [dashboard, sample]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--redo", action="store_true", help="classifica tudo de novo")
    parser.add_argument("--skip-classification", action="store_true", help="só refaz os números")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_level)
    model_id = settings.llm_model_id
    bucket = os.environ["INDEX_BUCKET"]

    with connect(settings) as conn:
        ensure_themes_table(conn)
        if not args.skip_classification:
            pending = [
                ReviewText(review_id, text)
                for review_id, text in read_texts_to_classify(conn, redo=args.redo)
            ]
            logger.info("etapa=temas pendentes=%d modelo=%s", len(pending), model_id)
            client = boto3.client(
                "bedrock-runtime",
                region_name=settings.aws_region,
                config=Config(retries={"mode": "adaptive", "max_attempts": 8}, read_timeout=60),
            )
            _, stats = classify_reviews(
                pending,
                lambda message: converse(client, model_id, message),
                workers=args.workers,
                on_batch=lambda themes: write_themes(conn, themes, model_id),
            )
            cost = (stats.input_tokens * PRICE_INPUT + stats.output_tokens * PRICE_OUTPUT) / 1e6
            logger.info(
                "etapa=temas_fim classificadas=%d sem_resposta=%d lotes=%d lotes_incompletos=%d "
                "tokens_entrada=%d tokens_saida=%d custo_usd=%.2f",
                stats.classified,
                len(stats.unclassified),
                stats.batches,
                stats.failed_batches,
                stats.input_tokens,
                stats.output_tokens,
                cost,
            )
        rows = to_rows(read_review_rows(conn))

    with_theme = sum(bool(row.themes) for row in rows)
    logger.info("etapa=painel avaliacoes=%d com_tema=%d", len(rows), with_theme)
    s3 = boto3.client("s3", region_name=settings.aws_region)
    with tempfile.TemporaryDirectory() as tmp:
        for path in write_outputs(rows, model_id, Path(tmp)):
            s3.upload_file(str(path), bucket, f"{RESULTS_PREFIX}/{path.name}")
    logger.info("etapa=painel destino=s3://%s/%s", bucket, RESULTS_PREFIX)


if __name__ == "__main__":
    main()
