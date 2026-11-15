"""Carrega os embeddings do S3 no PostgreSQL."""

from pathlib import Path

from src.config import Settings
from src.vector_store import IndexManifest


def load_vectors(conn, index_dir: Path, settings: Settings) -> IndexManifest:
    raise NotImplementedError
