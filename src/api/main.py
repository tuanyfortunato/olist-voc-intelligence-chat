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

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.api.auth import require_access_key
from src.api.quota import DailyQuota
from src.api.schemas import AskRequest, AskResponse
from src.config import Settings, get_settings
from src.logging_config import setup_logging
from src.rag.pipeline import RagPipeline, build_pipeline
from src.rag.schemas import ConversationTurn
from src.vector_db import IndexStatus, connect, read_index_status
from src.vector_store import check_manifest

logger = logging.getLogger(__name__)

StatusProvider = Callable[[], IndexStatus]

QUOTA_EXCEEDED = "Limite diário de perguntas atingido."
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
    quota: DailyQuota | None = None,
) -> FastAPI:
    """Monta a API. Os testes passam um pipeline e uma cota próprios, sem AWS."""
    settings = settings or get_settings()
    status_provider = status_provider or database_status_provider(settings)
    quota = quota or DailyQuota(settings.daily_question_limit)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging(settings.log_level)
        # Sem banco, sem manifesto ou com um índice diferente da configuração,
        # a API não sobe: o erro aparece no log da tarefa, e não nas respostas.
        status = status_provider()
        check_manifest(status.manifest, settings, status.documents)
        app.state.pipeline = pipeline or build_pipeline(settings)
        logger.info("etapa=inicio documentos=%d", status.documents)
        yield

    app = FastAPI(title="Olist VoC Intelligence Chat", lifespan=lifespan)
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
    # Bedrock e ao banco não travam as outras requisições. A chave é conferida
    # antes do corpo, e a cota só é descontada depois dos dois.
    @app.post("/api/ask", response_model=AskResponse, dependencies=[Depends(require_access_key)])
    def ask(body: AskRequest):
        if not quota.consume():
            logger.warning("etapa=cota limite=%d", quota.limit)
            raise HTTPException(status_code=429, detail=QUOTA_EXCEEDED)
        history = [ConversationTurn(turn.question, turn.answer) for turn in body.history]
        try:
            result = app.state.pipeline.ask(body.question, history)
        except (ClientError, BotoCoreError):
            logger.exception("etapa=pergunta erro=bedrock")
            raise HTTPException(status_code=503, detail=MODELS_UNAVAILABLE) from None
        except Exception:
            logger.exception("etapa=pergunta erro=inesperado")
            raise HTTPException(status_code=500, detail=UNEXPECTED_ERROR) from None
        return asdict(result)

    return app
