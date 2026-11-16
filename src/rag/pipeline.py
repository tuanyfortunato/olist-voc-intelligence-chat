"""Fluxo de uma pergunta, da mensagem do gestor até a resposta com as evidências.

A ordem é: análise da pergunta (escopo e reescrita), embedding do tema da
busca, busca no PostgreSQL com score mínimo e MMR, geração da resposta só com
os comentários recuperados e leitura das citações. O histórico da conversa vai
apenas para a análise da pergunta; a geração da resposta nunca o recebe.
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, replace

from src.config import Settings
from src.rag.context_builder import extract_citations, remove_invalid_citations
from src.rag.generator import generate_answer
from src.rag.prompts import (
    GREETING_MESSAGE,
    NO_EVIDENCE_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
    PREMISE_NOTE,
)
from src.rag.question_analysis import analyze_question
from src.rag.schemas import AskResult, ConversationTurn, RetrievedReview, SearchFilters

logger = logging.getLogger(__name__)

EmbedFunction = Callable[[str], list[float]]
SearchFunction = Callable[[list[float], SearchFilters | None], list[RetrievedReview]]
CountFunction = Callable[[SearchFilters | None], int]


# Até 2 avaliações citadas, a resposta sai com aviso de evidência fraca
WEAK_EVIDENCE_MAX_CITED = 2

FIXED_MESSAGES = {"out_of_scope": OUT_OF_SCOPE_MESSAGE, "greeting": GREETING_MESSAGE}


def decide_status(
    n_retrieved: int, n_cited: int, top_similarity: float = 1.0, strong_similarity: float = 0.0
) -> str:
    """Situação da resposta a partir das avaliações recuperadas, das citadas e do score.

    Nenhuma recuperada ou nenhuma citada vale como sem evidência. A evidência é
    fraca quando a resposta cita uma ou duas avaliações, ou quando nem o
    comentário mais próximo chega ao score de evidência forte. O segundo sinal
    existe porque o modelo tende a citar quase todos os comentários que parecem
    próximos: na pergunta sobre embalagem de presente, citou dez quando só um
    era relevante.
    """
    if n_retrieved == 0 or n_cited == 0:
        return "no_evidence"
    if n_cited <= WEAK_EVIDENCE_MAX_CITED or top_similarity < strong_similarity:
        return "weak_evidence"
    return "answered"


class RagPipeline:
    def __init__(
        self,
        settings: Settings,
        analysis_llm,
        answer_llm,
        embed: EmbedFunction,
        search: SearchFunction,
        count: CountFunction | None = None,
    ):
        self.settings = settings
        self.analysis_llm = analysis_llm
        self.answer_llm = answer_llm
        self.embed = embed
        self.search = search
        self.count = count

    def scope_count(self, filters: SearchFilters | None) -> int | None:
        """Tamanho do recorte da busca. Uma falha aqui não derruba a resposta."""
        if self.count is None:
            return None
        try:
            return self.count(filters)
        except Exception:
            logger.warning("etapa=recorte erro=contagem", exc_info=True)
            return None

    def ask(
        self,
        question: str,
        history: list[ConversationTurn] | None = None,
        filters: SearchFilters | None = None,
    ) -> AskResult:
        timings = {}
        start = time.monotonic()
        result = analyze_question(question, history or [], self.analysis_llm)
        analysis = result.analysis
        timings["analise_ms"] = (time.monotonic() - start) * 1000

        if analysis.kind in FIXED_MESSAGES:
            logger.info("etapa=pergunta original=%r tipo=%s", question, analysis.kind)
            return AskResult(
                status=analysis.kind,
                answer=FIXED_MESSAGES[analysis.kind],
                cited=[],
                uncited=[],
                original_question=question,
                search_topic="",
            )

        # As notas mencionadas na pergunta viram filtro quando o gestor não marcou
        # nenhuma nota no painel; a escolha do painel sempre vale mais
        inferred_ratings = []
        if analysis.ratings and not (filters and filters.ratings):
            inferred_ratings = analysis.ratings
            filters = replace(filters or SearchFilters(), ratings=inferred_ratings)

        topic = analysis.search_topic if self.settings.use_rewrite else question
        start = time.monotonic()
        retrieved = self.search(self.embed(topic), filters)
        timings["busca_ms"] = (time.monotonic() - start) * 1000
        reviews = [replace(review, number=n) for n, review in enumerate(retrieved, start=1)]
        scope_count = self.scope_count(filters)

        # Nenhum comentário passou do score mínimo: responde sem chamar o modelo
        if not reviews:
            logger.info("etapa=pergunta original=%r tema=%r recuperados=0", question, topic)
            return AskResult(
                status="no_evidence",
                answer=NO_EVIDENCE_MESSAGE,
                cited=[],
                uncited=[],
                original_question=question,
                search_topic=topic,
                inferred_ratings=inferred_ratings,
                scope_count=scope_count,
            )

        start = time.monotonic()
        answer = generate_answer(analysis.clean_question, reviews, self.answer_llm)
        timings["geracao_ms"] = (time.monotonic() - start) * 1000

        check = extract_citations(answer, len(reviews))
        if check.invalid:
            logger.warning("etapa=citacoes invalidas=%s", check.invalid)
            answer = remove_invalid_citations(answer, check.invalid)
        by_number = {review.number: review for review in reviews}
        cited = [by_number[n] for n in check.cited]
        uncited = [review for review in reviews if review.number not in check.cited]

        top_similarity = max(review.similarity for review in reviews)
        status = decide_status(
            len(reviews), len(cited), top_similarity, self.settings.strong_similarity
        )
        # O modelo às vezes marca uma premissa sem ter tirado nada da pergunta;
        # o aviso só entra quando a pergunta limpa de fato mudou
        premise_removed = (
            analysis.removed_premise and analysis.clean_question.strip() != question.strip()
        )
        if premise_removed and status != "no_evidence":
            answer = f"{answer}\n\n{PREMISE_NOTE}"
        logger.info(
            "etapa=pergunta original=%r tema=%r situacao=%s recuperados=%d citados=%d %s",
            question,
            topic,
            status,
            len(reviews),
            len(cited),
            " ".join(f"{k}={v:.0f}" for k, v in timings.items()),
        )
        return AskResult(
            status=status,
            answer=answer,
            cited=cited,
            uncited=uncited,
            original_question=question,
            search_topic=topic,
            inferred_ratings=inferred_ratings,
            scope_count=scope_count,
        )


def build_pipeline(settings: Settings) -> RagPipeline:
    """Monta o pipeline com os modelos do Bedrock e a busca no PostgreSQL."""
    from src.aws.bedrock import embed_query, get_chat_model, get_runtime_client
    from src.rag.retriever import count_in_scope, retrieve
    from src.vector_db import connect

    client = get_runtime_client(settings)

    def search(embedding: list[float], filters: SearchFilters | None) -> list[RetrievedReview]:
        with connect(settings) as conn:
            return retrieve(conn, embedding, settings, filters)

    # A base não muda enquanto a API roda: cada recorte é contado uma vez só
    counts: dict[str, int] = {}

    def count(filters: SearchFilters | None) -> int:
        key = json.dumps(asdict(filters) if filters else {}, sort_keys=True)
        if key not in counts:
            with connect(settings) as conn:
                counts[key] = count_in_scope(conn, filters)
        return counts[key]

    return RagPipeline(
        settings=settings,
        analysis_llm=get_chat_model(settings, settings.analysis_max_tokens),
        answer_llm=get_chat_model(
            settings, settings.answer_max_tokens, model_id=settings.answer_model_id
        ),
        embed=lambda text: embed_query(client, text, settings),
        search=search,
        count=count,
    )
