"""API do chat.

O /api/health é usado pelo ALB para saber se a tarefa está pronta. O
/api/ask recebe a pergunta da página e devolve a resposta com as avaliações
citadas e as recuperadas sem citação.

Uso, a partir da raiz do projeto:
    uvicorn src.api.main:create_app --factory --host 0.0.0.0 --port 8000
"""

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import asdict

import psycopg
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.rate_limit import QuestionLimiter, build_limiter, client_ip, refusal_message
from src.api.schemas import AskRequest, AskResponse
from src.config import Settings, get_settings
from src.logging_config import setup_logging
from src.rag.pipeline import RagPipeline, build_pipeline
from src.rag.schemas import ConversationTurn, SearchFilters
from src.vector_db import IndexStatus, connect, read_index_status
from src.vector_store import check_manifest

logger = logging.getLogger(__name__)

StatusProvider = Callable[[], IndexStatus]

MODELS_UNAVAILABLE = (
    "O serviço de modelos está indisponível no momento. Tente de novo em alguns segundos."
)
UNEXPECTED_ERROR = "Não foi possível responder a pergunta. Tente de novo mais tarde."


def database_status_provider(settings: Settings) -> StatusProvider:
    def provider() -> IndexStatus:
        with connect(settings) as conn:
            return read_index_status(conn)

    return provider


def create_app(
    settings: Settings | None = None,
    status_provider: StatusProvider | None = None,
    pipeline: RagPipeline | None = None,
    limiter: QuestionLimiter | None = None,
) -> FastAPI:
    """Monta a API. Os testes passam um pipeline e um limitador próprios, sem AWS
    e sem banco."""
    settings = settings or get_settings()
    status_provider = status_provider or database_status_provider(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging(settings.log_level)
        # Sem banco, sem manifesto ou com um índice diferente da configuração,
        # a API não sobe: o erro aparece no log da tarefa, e não nas respostas.
        status = status_provider()
        check_manifest(status.manifest, settings, status.documents)
        app.state.pipeline = pipeline or build_pipeline(settings)
        app.state.limiter = limiter or build_limiter(settings)
        app.state.categories = status.manifest.categories
        logger.info("etapa=inicio documentos=%d", status.documents)
        yield

    app = FastAPI(title="Olist Intelligence Chat", lifespan=lifespan)
    app.state.settings = settings

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

    # Função síncrona: o FastAPI a roda no pool de threads, e as chamadas ao
    # Bedrock e ao banco não travam as outras requisições. O limite só é
    # descontado depois que o corpo passa na validação.
    @app.post("/api/ask", response_model=AskResponse)
    def ask(body: AskRequest, request: Request):
        check_limits(request)
        history = [ConversationTurn(turn.question, turn.answer) for turn in body.history]
        filters = SearchFilters(**body.filters.model_dump()) if body.filters else None
        try:
            result = app.state.pipeline.ask(body.question, history, filters)
        except (ClientError, BotoCoreError):
            logger.exception("etapa=pergunta erro=bedrock")
            raise HTTPException(status_code=503, detail=MODELS_UNAVAILABLE) from None
        except Exception:
            logger.exception("etapa=pergunta erro=inesperado")
            raise HTTPException(status_code=500, detail=UNEXPECTED_ERROR) from None
        return asdict(result)

    def check_limits(request: Request) -> None:
        ip = client_ip(request, settings.proxy_hops)
        try:
            refusal = app.state.limiter.consume(ip)
        except psycopg.Error:
            logger.exception("etapa=limite erro=banco")
            raise HTTPException(status_code=503, detail=UNEXPECTED_ERROR) from None
        if refusal:
            # O IP não vai para o log, só qual limite foi atingido
            logger.warning("etapa=limite motivo=%s limite=%d", refusal.reason, refusal.limit)
            wait = max(1, int((refusal.retry_at - app.state.limiter.now()).total_seconds()))
            raise HTTPException(
                status_code=429,
                detail=refusal_message(refusal),
                headers={"Retry-After": str(wait)},
            )

    # Categorias para o filtro da página, vindas do manifesto dos embeddings
    @app.get("/api/categories")
    def categories():
        return {"categories": app.state.categories}

    return app
