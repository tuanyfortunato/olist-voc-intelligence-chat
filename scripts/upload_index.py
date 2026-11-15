"""Envia os embeddings e o manifesto para o S3, substituindo a versão anterior.

Uso, a partir da raiz do projeto, com a variável INDEX_BUCKET definida:
    python -m scripts.upload_index
"""

import logging
import os
from pathlib import Path

import boto3

from src.config import get_settings
from src.logging_config import setup_logging

logger = logging.getLogger(__name__)

INDEX_PREFIX = "index/current"

# Só os arquivos finais vão para o S3; as partes intermediárias ficam no runner
FINAL_FILES = ["embeddings.parquet", "manifest.json"]


def upload_index(index_dir: Path, bucket: str, prefix: str = INDEX_PREFIX, s3=None) -> int:
    """Apaga o que houver no prefixo e envia os arquivos finais de index_dir. Devolve quantos."""
    s3 = s3 or boto3.client("s3", region_name=get_settings().aws_region)

    old_keys = [
        obj["Key"]
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=f"{prefix}/")
        for obj in page.get("Contents", [])
    ]
    for start in range(0, len(old_keys), 1000):
        chunk = old_keys[start : start + 1000]
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": key} for key in chunk]})

    files = [Path(index_dir) / name for name in FINAL_FILES]
    for path in files:
        s3.upload_file(str(path), bucket, f"{prefix}/{path.name}")
    logger.info(
        "etapa=envio_indice arquivos=%d removidos=%d destino=s3://%s/%s",
        len(files),
        len(old_keys),
        bucket,
        prefix,
    )
    return len(files)


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    upload_index(Path(settings.index_dir), os.environ["INDEX_BUCKET"])


if __name__ == "__main__":
    main()
