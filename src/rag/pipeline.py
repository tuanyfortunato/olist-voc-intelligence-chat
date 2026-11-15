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
from src.rag.question_analysis import analyze_question
from src.rag.schemas import AskResult, ConversationTurn, RetrievedReview

logger = logging.getLogger(__name__)

EmbedFunction = Callable[[str], list[float]]
SearchFunction = Callable[[list[float]], list[RetrievedReview]]


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

        topic = analysis.search_topic if self.settings.use_rewrite else question
        start = time.monotonic()
        retrieved = self.search(self.embed(topic))
        timings["busca_ms"] = (time.monotonic() - start) * 1000
        reviews = [replace(review, number=n) for n, review in enumerate(retrieved, start=1)]

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

        logger.info(
            "etapa=pergunta original=%r tema=%r recuperados=%d citados=%d %s",
            question,
            topic,
            len(reviews),
            len(cited),
            " ".join(f"{k}={v:.0f}" for k, v in timings.items()),
        )
        return AskResult(
            status="answered",
            answer=answer,
            cited=cited,
            uncited=uncited,
            original_question=question,
            search_topic=topic,
        )
