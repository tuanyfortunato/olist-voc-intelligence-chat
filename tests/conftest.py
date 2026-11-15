import pytest

from src.config import Settings


@pytest.fixture
def settings():
    """Configuração com os valores padrão, sem ler variáveis de ambiente."""
    return Settings()
