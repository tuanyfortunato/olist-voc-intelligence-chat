"""Envia o índice do Chroma e o manifesto para o S3, substituindo a versão anterior.

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


def upload_index(index_dir: Path, bucket: str, prefix: str = INDEX_PREFIX, s3=None) -> int:
    """Apaga o que houver no prefixo e envia todos os arquivos de index_dir. Devolve quantos."""
    s3 = s3 or boto3.client("s3", region_name=get_settings().aws_region)

    old_keys = [
        obj["Key"]
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=f"{prefix}/")
        for obj in page.get("Contents", [])
    ]
    for start in range(0, len(old_keys), 1000):
        chunk = old_keys[start : start + 1000]
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": key} for key in chunk]})

    files = [path for path in Path(index_dir).rglob("*") if path.is_file()]
    for path in files:
        key = f"{prefix}/{path.relative_to(index_dir).as_posix()}"
        s3.upload_file(str(path), bucket, key)
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
