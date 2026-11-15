"""Banco vetorial: PostgreSQL com a extensão pgvector.

A tabela reviews guarda, para cada avaliação, o vetor gerado pelo Cohere, o
texto e os metadados usados nos filtros. A busca usa um índice HNSW com
distância de cosseno. A tabela index_manifest guarda uma única linha com o
manifesto dos embeddings carregados, que a API confere ao iniciar.
"""

import json
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import psycopg
from pgvector.psycopg import register_vector

from src.config import Settings
from src.vector_store import IndexManifest

COLUMNS = [
    "review_id",
    "embedding",
    "embedding_text",
    "original_text",
    "rating",
    "review_date",
    "category",
    "delivery",
    "order_id",
    "text_length",
]
COLUMN_TYPES = ["text", "vector", "text", "text", "int4", "text", "text", "text", "text", "int4"]
INDEX_NAME = "reviews_embedding_idx"


@dataclass(frozen=True)
class IndexStatus:
    manifest: IndexManifest
    documents: int


def connect(settings: Settings, register: bool = True) -> psycopg.Connection:
    """Abre a conexão. Com register=True, já reconhece o tipo vector do pgvector,
    o que exige a extensão criada; a carga usa register=False antes de criá-la."""
    conn = psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        sslmode=settings.db_sslmode,
        connect_timeout=10,
    )
    if register:
        register_vector(conn)
    return conn


def ensure_schema(conn: psycopg.Connection, dimensions: int) -> None:
    """Cria a extensão e as tabelas, se ainda não existirem."""
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS reviews (
            review_id text PRIMARY KEY,
            embedding vector({int(dimensions)}) NOT NULL,
            embedding_text text NOT NULL,
            original_text text NOT NULL,
            rating int NOT NULL,
            review_date text NOT NULL,
            category text NOT NULL,
            delivery text NOT NULL,
            order_id text NOT NULL,
            text_length int NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS index_manifest (
            id int PRIMARY KEY DEFAULT 1 CHECK (id = 1),
            data jsonb NOT NULL
        )
        """
    )
    conn.commit()
    register_vector(conn)


def load_reviews(conn: psycopg.Connection, frame: pd.DataFrame) -> int:
    """Substitui o conteúdo da tabela reviews pelo do DataFrame e recria o índice HNSW.

    Tudo acontece numa transação: se a carga falhar no meio, o conteúdo
    anterior continua lá. O índice é criado depois da carga, que assim fica
    bem mais rápida.
    """
    with conn.transaction():
        conn.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
        conn.execute("TRUNCATE reviews")
        with conn.cursor() as cur:
            columns = ", ".join(COLUMNS)
            with cur.copy(f"COPY reviews ({columns}) FROM STDIN WITH (FORMAT BINARY)") as copy:
                copy.set_types(COLUMN_TYPES)
                for row in frame[COLUMNS].itertuples(index=False):
                    values = list(row)
                    values[1] = np.asarray(values[1], dtype=np.float32)
                    copy.write_row(values)
        # Memória extra só para esta sessão, para o índice ser construído de uma vez
        conn.execute("SET LOCAL maintenance_work_mem = '256MB'")
        conn.execute(
            f"CREATE INDEX {INDEX_NAME} ON reviews USING hnsw (embedding vector_cosine_ops)"
        )
    conn.execute("ANALYZE reviews")
    conn.commit()
    return count_reviews(conn)


def count_reviews(conn: psycopg.Connection) -> int:
    return conn.execute("SELECT count(*) FROM reviews").fetchone()[0]


def write_manifest_row(conn: psycopg.Connection, manifest: IndexManifest) -> None:
    conn.execute(
        """
        INSERT INTO index_manifest (id, data) VALUES (1, %s)
        ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data
        """,
        (json.dumps(asdict(manifest), ensure_ascii=False),),
    )
    conn.commit()


def read_manifest_row(conn: psycopg.Connection) -> IndexManifest:
    row = conn.execute("SELECT data FROM index_manifest WHERE id = 1").fetchone()
    if row is None:
        raise LookupError("O banco ainda não tem manifesto: rode o workflow Load vectors.")
    return IndexManifest.from_dict(row[0])


def read_index_status(conn: psycopg.Connection) -> IndexStatus:
    """Manifesto e número de linhas do banco, usados pela API ao iniciar e no /api/health."""
    return IndexStatus(manifest=read_manifest_row(conn), documents=count_reviews(conn))
