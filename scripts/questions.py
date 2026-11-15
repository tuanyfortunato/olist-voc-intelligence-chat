"""Leitura das perguntas de teste de evaluation/questions.yaml.

Usado pela calibração da busca e pela avaliação das respostas.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

QUESTIONS_PATH = Path("evaluation/questions.yaml")

QUESTION_TYPES = {
    "with_evidence",
    "no_evidence",
    "weak_evidence",
    "out_of_scope",
    "false_premise",
    "rule_change",
    "greeting_follow_up",
    "with_filter",
}


@dataclass(frozen=True)
class TestQuestion:
    id: int
    question: str
    type: str
    expected: str
    turns: list[str] = field(default_factory=list)
    history_from: int | None = None
    filters: dict = field(default_factory=dict)


def load_questions(path: Path = QUESTIONS_PATH, ids: list[int] | None = None) -> list[TestQuestion]:
    with open(path, encoding="utf-8") as file:
        questions = [TestQuestion(**item) for item in yaml.safe_load(file)]
    unknown = {q.type for q in questions} - QUESTION_TYPES
    if unknown:
        raise ValueError(f"Tipos de pergunta desconhecidos: {unknown}")
    if ids is not None:
        questions = [q for q in questions if q.id in ids]
    return questions
