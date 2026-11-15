"""Geração da resposta com o Nova Micro (camada 3 de proteção)."""

import logging

from src.rag.context_builder import build_context
from src.rag.prompts import build_answer_messages
from src.rag.schemas import RetrievedReview

logger = logging.getLogger(__name__)


def generate_answer(clean_question: str, reviews: list[RetrievedReview], llm) -> str:
    messages = build_answer_messages(clean_question, build_context(reviews))
    logger.debug("etapa=geracao mensagens=%r", messages)
    answer = llm.invoke(messages).content
    logger.debug("etapa=geracao resposta=%r", answer)
    return answer
