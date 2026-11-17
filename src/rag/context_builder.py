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


# "Vários clientes", "muitas avaliações": quantidade que pede mais de dois
# comentários citados na mesma frase
QUANTITY_PATTERN = re.compile(
    r"\b(v[aá]ri|muit|divers|in[uú]mer)(os|as)(\s+(?:clientes|compradores|consumidores|"
    r"pessoas|usu[aá]rios|avalia[cç][oõ]es|coment[aá]rios|relatos|reclama[cç][oõ]es|casos))\b",
    re.IGNORECASE,
)
# Palavras que dizem que o problema se repete
RECURRENCE_PATTERN = re.compile(
    r"\s*\b(?:de\s+(?:forma|maneira)\s+recorrente|recorrentes?|recorrentemente|"
    r"com\s+frequ[eê]ncia|frequentemente|frequentes?|repetidamente)\b",
    re.IGNORECASE,
)
# "São recorrentes", "é frequente": tirar só o adjetivo deixaria a frase sem verbo,
# então o trecho vira "aparecem nos comentários"
RECURRENCE_PREDICATE = re.compile(
    r"\b(é|são|foi|foram)\s+(?:recorrentes?|frequentes?)\b",
    re.IGNORECASE,
)
PREDICATE_REPLACEMENT = {
    "é": "aparece",
    "são": "aparecem",
    "foi": "apareceu",
    "foram": "apareceram",
}
# Sinais, no texto do cliente, de que o problema aconteceu mais de uma vez
REPETITION_CUE = re.compile(
    r"\b(?:novamente|de\s+novo|outra\s+vez|mais\s+uma\s+vez|sempre|toda\s+vez|"
    r"todas\s+as\s+vezes|segunda\s+vez|terceira\s+vez|v[aá]rias\s+vezes|"
    r"repetid\w*|recorrent\w*|n[aã]o\s+[eé]\s+a\s+primeira)\b",
    re.IGNORECASE,
)
# A partir de quantos comentários citados uma frase pode falar em "vários" ou
# em problema recorrente entre clientes
MIN_CITATIONS_FOR_MANY = 3


def soften_unsupported_quantities(answer: str, reviews: list[RetrievedReview]) -> str:
    """Suaviza "vários clientes" e "problemas recorrentes" que os comentários não sustentam.

    O modelo às vezes escreve "vários clientes relatam problemas recorrentes"
    citando um ou dois comentários, e às vezes um comentário que diz que foi a
    primeira vez. Frase a frase, com menos de três comentários citados, "vários"
    vira "alguns" e a palavra de repetição sai, a não ser que algum comentário
    citado diga que o problema se repetiu. Frases sem citação ficam como estão,
    porque não há o que conferir.
    """
    by_number = {review.number: review for review in reviews}
    lines = []
    for line in answer.split("\n"):
        sentences = SENTENCE_END.split(line)
        lines.append(" ".join(_soften_sentence(s, by_number) for s in sentences))
    return "\n".join(lines)


def _soften_sentence(sentence: str, by_number: dict[int, RetrievedReview]) -> str:
    cited = {
        n
        for match in CITATION_PATTERN.finditer(sentence)
        for n in _numbers(match.group(1))
        if n in by_number
    }
    if not cited or len(cited) >= MIN_CITATIONS_FOR_MANY:
        return sentence

    softened = QUANTITY_PATTERN.sub(_to_some, sentence)
    repeated = any(REPETITION_CUE.search(by_number[n].original_text) for n in cited)
    if not repeated:
        softened = RECURRENCE_PREDICATE.sub(_to_appears, softened)
        softened = RECURRENCE_PATTERN.sub("", softened)
        softened = re.sub(r"\s+([.,;:!?])", r"\1", softened)
        softened = re.sub(r"[ \t]{2,}", " ", softened)
    return softened


def _to_some(match: re.Match) -> str:
    word = "alguns" if match.group(2).lower() == "os" else "algumas"
    if match.group(1)[0].isupper():
        word = word.capitalize()
    return word + match.group(3)


def _to_appears(match: re.Match) -> str:
    verb = PREDICATE_REPLACEMENT[match.group(1).lower()]
    if match.group(1)[0].isupper():
        verb = verb.capitalize()
    return verb + " nos comentários"


# Linha que é só um rótulo seguido de citações, como "Atraso na entrega: [1][2]"
LABEL_ONLY_LINE = re.compile(r"^\s*(?:[-•*]\s*)?([^:\n]{1,80}):\s*$")


def is_label_only_list(answer: str) -> bool:
    """Diz se a resposta é só uma lista de rótulos com citações, sem nenhuma frase."""
    lines = [line for line in answer.split("\n") if line.strip()]
    if not lines:
        return False
    return all(LABEL_ONLY_LINE.match(CITATION_PATTERN.sub("", line)) for line in lines)


def labels_to_sentence(answer: str) -> str:
    """Junta uma lista de rótulos com citações numa frase só, mantendo as citações.

    "- Atraso na entrega: [1][2]" e "- Falha na entrega: [5]" viram "Nos comentários
    recuperados aparecem estes temas: atraso na entrega [1][2] e falha na entrega [5]."
    """
    items = []
    for line in answer.split("\n"):
        citations = "".join(match.group(0) for match in CITATION_PATTERN.finditer(line))
        match = LABEL_ONLY_LINE.match(CITATION_PATTERN.sub("", line))
        if not match:
            continue
        label = match.group(1).strip()
        if len(label) > 1 and not label[:2].isupper():
            label = label[0].lower() + label[1:]
        items.append(f"{label} {citations}".strip())
    if len(items) > 1:
        listed = ", ".join(items[:-1]) + " e " + items[-1]
    else:
        listed = items[0]
    return f"Nos comentários recuperados aparecem estes temas: {listed}."
