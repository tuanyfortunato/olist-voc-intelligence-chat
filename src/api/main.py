"""API do chat.

Nesta versão a API só responde ao /api/health, que o ALB usa para saber se a
tarefa está pronta. As rotas da pergunta entram nas próximas etapas.

Uso, a partir da raiz do projeto:
    uvicorn src.api.main:create_app --factory --host 0.0.0.0 --port 8000
"""

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.config import Settings, get_settings
from src.logging_config import setup_logging
from src.vector_db import IndexStatus, connect, read_index_status
from src.vector_store import check_manifest

logger = logging.getLogger(__name__)

StatusProvider = Callable[[], IndexStatus]


def database_status_provider(settings: Settings) -> StatusProvider:
    def provider() -> IndexStatus:
        with connect(settings) as conn:
            return read_index_status(conn)

    return provider


def create_app(
    settings: Settings | None = None, status_provider: StatusProvider | None = None
) -> FastAPI:
    settings = settings or get_settings()
    status_provider = status_provider or database_status_provider(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging(settings.log_level)
        # Sem banco, sem manifesto ou com um índice diferente da configuração,
        # a API não sobe: o erro aparece no log da tarefa, e não nas respostas.
        status = status_provider()
        check_manifest(status.manifest, settings, status.documents)
        logger.info("etapa=inicio documentos=%d", status.documents)
        yield

    app = FastAPI(title="Olist VoC Intelligence Chat", lifespan=lifespan)

    @app.get("/api/health")
    def health():
        try:
            status = status_provider()
        except Exception:
            logger.exception("etapa=health erro=banco_indisponivel")
            return JSONResponse(status_code=503, content={"status": "banco indisponível"})
        return {
            "status": "ok",
            "documents": status.documents,
            "embedding_model": status.manifest.embedding_model_id,
            "index_created_at": status.manifest.created_at,
        }

    return app
