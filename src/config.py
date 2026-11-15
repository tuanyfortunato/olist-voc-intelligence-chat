"""Configuração do projeto.

Todos os valores têm um padrão e podem ser trocados por variáveis de ambiente,
lidas também do arquivo .env quando ele existe. Na AWS, as variáveis vêm da
definição da tarefa do ECS.
"""

import os
from dataclasses import dataclass, fields
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    # AWS e modelos
    aws_region: str = "us-east-1"
    embedding_model_id: str = "cohere.embed-multilingual-v3"
    embedding_dimensions: int = 1024
    embedding_batch_size: int = 96
    llm_model_id: str = "amazon.nova-micro-v1:0"

    # Embeddings gerados pela indexação
    index_dir: str = "data/index"
    index_workers: int = 2

    # Banco vetorial (RDS PostgreSQL com pgvector). Na AWS, o host vem da
    # definição da tarefa e a senha, do Parameter Store.
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "olist"
    db_user: str = "olist"
    db_password: str = ""
    db_sslmode: str = "require"

    # Recuperação. O score mínimo, o top-k e o corte dos comentários curtos
    # são calibrados na etapa 5.
    candidates_k: int = 40
    top_k: int = 15
    min_similarity: float = 0.0
    mmr_lambda: float = 0.5
    min_comment_chars: int = 0

    # Geração
    analysis_max_tokens: int = 300
    answer_max_tokens: int = 800

    # Limites da API
    max_question_chars: int = 500
    history_turns: int = 3
    history_answer_chars: int = 1500
    daily_question_limit: int = 300
    access_key: str = ""

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Monta a configuração a partir do ambiente, convertendo cada valor para o tipo do campo."""
    load_dotenv()
    values = {}
    for field in fields(Settings):
        raw = os.getenv(field.name.upper())
        if raw is not None:
            values[field.name] = type(field.default)(raw)
    return Settings(**values)
