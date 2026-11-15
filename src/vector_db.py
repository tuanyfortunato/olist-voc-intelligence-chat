"""Banco vetorial: PostgreSQL com pgvector."""

import pandas as pd

from src.vector_store import IndexManifest


def ensure_schema(conn, dimensions: int) -> None:
    raise NotImplementedError


def load_reviews(conn, frame: pd.DataFrame) -> int:
    raise NotImplementedError


def count_reviews(conn) -> int:
    raise NotImplementedError


def write_manifest_row(conn, manifest: IndexManifest) -> None:
    raise NotImplementedError


def read_manifest_row(conn) -> IndexManifest:
    raise NotImplementedError
