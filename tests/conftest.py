import pytest

from src.config import Settings


@pytest.fixture
def settings():
    """Configuração com os valores padrão, sem ler variáveis de ambiente."""
    return Settings()


@pytest.fixture
def pg_conn():
    """Conexão com o PostgreSQL de teste num schema próprio, já com as tabelas.
    Os testes que usam esta fixture são pulados quando não há TEST_DATABASE_URL."""
    import os
    import uuid

    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("sem TEST_DATABASE_URL")

    import psycopg

    from src.vector_db import ensure_schema

    schema = f"teste_{uuid.uuid4().hex[:8]}"
    connection = psycopg.connect(url)
    connection.execute(f"CREATE SCHEMA {schema}")
    connection.execute(f"SET search_path TO {schema}, public")
    ensure_schema(connection, dimensions=3)
    yield connection
    connection.rollback()
    connection.execute(f"DROP SCHEMA {schema} CASCADE")
    connection.commit()
    connection.close()
