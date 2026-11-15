"""Contexto numerado para o prompt e leitura das citações da resposta.

Cada comentário recuperado recebe um número, começando em 1, e a resposta cita
os comentários por esse número, como em "Atrasos são comuns [1][4]". Depois da
geração, o código lê as citações para saber quais avaliações a resposta usou e
remove as que apontam para números que não existem.
"""

import re
from dataclasses import dataclass

from src.rag.schemas import RetrievedReview

# [3], [1,3] e [1, 3]; colchetes com texto, como [Lannister], ficam de fora
CITATION_PATTERN = re.compile(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]")


@dataclass(frozen=True)
class CitationCheck:
    cited: list[int]
    invalid: list[int]


def build_context(reviews: list[RetrievedReview]) -> str:
    return "\n".join(
        f"[{number}] (avaliação {review.review_id}, nota {review.rating}) {review.original_text}"
        for number, review in enumerate(reviews, start=1)
    )


def _numbers(group: str) -> list[int]:
    return [int(part) for part in group.split(",")]


def extract_citations(answer: str, n_reviews: int) -> CitationCheck:
    """Números citados na ordem em que aparecem, sem repetição, e os que não existem."""
    cited, invalid = [], []
    for match in CITATION_PATTERN.finditer(answer):
        for number in _numbers(match.group(1)):
            target = cited if 1 <= number <= n_reviews else invalid
            if number not in target:
                target.append(number)
    return CitationCheck(cited=cited, invalid=invalid)


def remove_invalid_citations(answer: str, invalid: list[int]) -> str:
    if not invalid:
        return answer

    def keep_valid(match: re.Match) -> str:
        valid = [n for n in _numbers(match.group(1)) if n not in invalid]
        return f"[{', '.join(str(n) for n in valid)}]" if valid else ""

    cleaned = CITATION_PATTERN.sub(keep_valid, answer)
    cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()
