"""Fluxo de uma pergunta, da mensagem do gestor até a resposta com as evidências.

A ordem é: análise da pergunta (escopo e reescrita), embedding do tema da
busca, busca no PostgreSQL com score mínimo e MMR, geração da resposta só com
os comentários recuperados e leitura das citações. O histórico da conversa vai
apenas para a análise da pergunta; a geração da resposta nunca o recebe.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import replace

from src.config import Settings
from src.rag.context_builder import extract_citations, remove_invalid_citations
from src.rag.generator import generate_answer
from src.rag.prompts import GREETING_MESSAGE, NO_EVIDENCE_MESSAGE, OUT_OF_SCOPE_MESSAGE
from src.rag.question_analysis import analyze_question
from src.rag.schemas import AskResult, ConversationTurn, RetrievedReview

logger = logging.getLogger(__name__)

EmbedFunction = Callable[[str], list[float]]
SearchFunction = Callable[[list[float]], list[RetrievedReview]]


# Até 2 avaliações citadas, a resposta sai com aviso de evidência fraca
WEAK_EVIDENCE_MAX_CITED = 2

FIXED_MESSAGES = {"out_of_scope": OUT_OF_SCOPE_MESSAGE, "greeting": GREETING_MESSAGE}


def decide_status(n_retrieved: int, n_cited: int) -> str:
    """Situação da resposta a partir das avaliações recuperadas e das citadas.

    Nenhuma recuperada ou nenhuma citada vale como sem evidência; uma ou duas
    citadas, evidência fraca. A medida é pelas citações, e não pelo score,
    porque o score não separa temas vizinhos: a busca pelo Pix traz comentários
    sobre pagamento em geral, com score parecido com o de comentários relevantes.
    """
    if n_retrieved == 0 or n_cited == 0:
        return "no_evidence"
    if n_cited <= WEAK_EVIDENCE_MAX_CITED:
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
    ):
        self.settings = settings
        self.analysis_llm = analysis_llm
        self.answer_llm = answer_llm
        self.embed = embed
        self.search = search

    def ask(self, question: str, history: list[ConversationTurn] | None = None) -> AskResult:
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

        topic = analysis.search_topic if self.settings.use_rewrite else question
        start = time.monotonic()
        retrieved = self.search(self.embed(topic))
        timings["busca_ms"] = (time.monotonic() - start) * 1000
        reviews = [replace(review, number=n) for n, review in enumerate(retrieved, start=1)]

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

        status = decide_status(len(reviews), len(cited))
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
        )


def build_pipeline(settings: Settings) -> RagPipeline:
    """Monta o pipeline com os modelos do Bedrock e a busca no PostgreSQL."""
    from src.aws.bedrock import embed_query, get_chat_model, get_runtime_client
    from src.rag.retriever import retrieve
    from src.vector_db import connect

    client = get_runtime_client(settings)

    def search(embedding: list[float]) -> list[RetrievedReview]:
        with connect(settings) as conn:
            return retrieve(conn, embedding, settings)

    return RagPipeline(
        settings=settings,
        analysis_llm=get_chat_model(settings, settings.analysis_max_tokens),
        answer_llm=get_chat_model(settings, settings.answer_max_tokens),
        embed=lambda text: embed_query(client, text, settings),
        search=search,
    )
