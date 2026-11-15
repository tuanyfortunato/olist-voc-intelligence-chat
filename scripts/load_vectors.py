"""Carrega os embeddings do S3 no PostgreSQL com pgvector.

Roda numa tarefa avulsa do ECS, disparada pelo workflow Load vectors, porque o
banco fica numa rede privada da AWS que o GitHub Actions não alcança.

Uso, a partir da raiz do projeto, com INDEX_BUCKET e as variáveis do banco definidas:
    python -m scripts.load_vectors
"""

import logging
import os
import tempfile
from pathlib import Path

import boto3

from src.config import Settings, get_settings
from src.knowledge_base.embedding_store import read_embeddings
from src.logging_config import setup_logging
from src.vector_db import connect, ensure_schema, load_reviews, write_manifest_row
from src.vector_store import IndexManifest, check_manifest, read_manifest

logger = logging.getLogger(__name__)

INDEX_PREFIX = "index/current"
FILES = ["embeddings.parquet", "manifest.json"]


def load_vectors(conn, index_dir: Path, settings: Settings) -> IndexManifest:
    """Grava no banco os embeddings de index_dir e o manifesto, conferindo a contagem."""
    manifest = read_manifest(index_dir)
    frame = read_embeddings(Path(index_dir) / "embeddings.parquet")
    ensure_schema(conn, settings.embedding_dimensions)
    count = load_reviews(conn, frame)
    check_manifest(manifest, settings, count)
    write_manifest_row(conn, manifest)
    logger.info("etapa=carga linhas=%d modelo=%s", count, manifest.embedding_model_id)
    return manifest


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    bucket = os.environ["INDEX_BUCKET"]
    s3 = boto3.client("s3", region_name=settings.aws_region)

    with tempfile.TemporaryDirectory() as tmp:
        for name in FILES:
            s3.download_file(bucket, f"{INDEX_PREFIX}/{name}", str(Path(tmp) / name))
        logger.info(
            "etapa=carga arquivos_baixados=%d origem=s3://%s/%s", len(FILES), bucket, INDEX_PREFIX
        )
        with connect(settings, register=False) as conn:
            load_vectors(conn, Path(tmp), settings)


if __name__ == "__main__":
    main()
