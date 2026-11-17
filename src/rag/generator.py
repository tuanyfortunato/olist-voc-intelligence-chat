"""Geração da resposta com o Nova Micro (camada 3 de proteção)."""

import logging
import re

from src.rag.context_builder import build_context
from src.rag.prompts import build_answer_messages
from src.rag.schemas import RetrievedReview

logger = logging.getLogger(__name__)

# O prompt pede texto simples, mas o Nova Micro às vezes devolve negrito e
# títulos em Markdown. A página mostra o texto como veio, então os asteriscos
# apareceriam na tela.
BOLD_PATTERN = re.compile(r"(\*\*|__)(.+?)\1", re.DOTALL)
HEADING_PATTERN = re.compile(r"^[ \t]*#{1,6}[ \t]+", re.MULTILINE)


def remove_markdown(answer: str) -> str:
    answer = BOLD_PATTERN.sub(r"\2", answer)
    answer = answer.replace("**", "")
    return HEADING_PATTERN.sub("", answer)


def generate_answer(clean_question: str, reviews: list[RetrievedReview], llm) -> str:
    messages = build_answer_messages(clean_question, build_context(reviews))
    logger.debug("etapa=geracao mensagens=%r", messages)
    answer = llm.invoke(messages).content
    logger.debug("etapa=geracao resposta=%r", answer)
    return remove_markdown(answer)
