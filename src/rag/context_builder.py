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


# Frase que diz que nenhum comentário fala do assunto, como "Nenhum dos
# comentários recuperados fala sobre o pagamento com Pix"
NEGATIVE_CLAIM_PATTERN = re.compile(
    r"\b(?:nenhum|nenhuma)\s+(?:d[oa]s\s+)?(?:coment[aá]rios?|avalia[cç](?:[aã]o|[oõ]es))\b",
    re.IGNORECASE,
)
# Fim de frase. Citações logo depois do ponto, como em "Pix. [1][2]", ficam com
# a frase anterior
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?!\[)")


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


def remove_citations_from_negative_claims(answer: str) -> str:
    """Tira as citações das frases que dizem que nenhum comentário fala do assunto.

    O modelo às vezes escreve "Nenhum dos comentários recuperados fala de Pix" e
    cita os 15 comentários na mesma frase. Uma frase assim não tem como ser
    sustentada por um comentário, e as citações fariam a resposta parecer ter
    evidência. Sem elas, a resposta que só diz isso sai como sem evidência.
    """
    lines = []
    for line in answer.split("\n"):
        sentences = SENTENCE_END.split(line)
        cleaned = [
            _strip_citations(sentence) if NEGATIVE_CLAIM_PATTERN.search(sentence) else sentence
            for sentence in sentences
        ]
        lines.append(" ".join(cleaned))
    return "\n".join(lines)


def _strip_citations(sentence: str) -> str:
    without = CITATION_PATTERN.sub("", sentence)
    without = re.sub(r"\s+([.,;:!?])", r"\1", without)
    return re.sub(r"[ \t]{2,}", " ", without).rstrip()
