import json

from scripts.questions import TestQuestion
from scripts.run_evaluation import evaluation_rows, parse_ids
from src.rag.schemas import AskResult, RetrievedReview


class FakePipeline:
    def ask(self, question, history=None):
        cited = [
            RetrievedReview("r1", 1, "bebes", "no_prazo", "2018-03-10", "Veio quebrado", 0.71, 1)
        ]
        uncited = [RetrievedReview("r2", 5, "bebes", "no_prazo", "2018-03-10", "Ótimo", 0.6, 2)]
        return AskResult("answered", "Quebrados [1].", cited, uncited, question, "defeitos")


def test_evaluation_rows():
    questions = [TestQuestion(2, "O que falam de defeito?", "with_evidence", "Resumo")]
    rows = evaluation_rows(questions, FakePipeline())
    row = rows[0]
    assert row["question_id"] == 2 and row["status"] == "answered"
    assert row["answer"] == "Quebrados [1]." and row["search_topic"] == "defeitos"
    assert row["cited_ids"] == "r1"
    retrieved = json.loads(row["retrieved_json"])
    assert [r["number"] for r in retrieved] == [1, 2]
    assert retrieved[0]["cited"] is True and retrieved[1]["cited"] is False
    assert row["latency_ms"] >= 0


def test_parse_ids():
    assert parse_ids("1,2, 7") == [1, 2, 7]
    assert parse_ids("") is None


class RecordingPipeline:
    def __init__(self):
        self.calls = []

    def ask(self, question, history=None):
        self.calls.append((question, history or []))
        return AskResult("answered", f"Resposta para {question} [1].", [], [], question, "tema")


def test_follow_up_question_runs_each_turn_with_history_from_earlier_question():
    from scripts.run_evaluation import MANUAL_COLUMNS

    questions = [
        TestQuestion(1, "Quais reclamações sobre entrega?", "with_evidence", "x"),
        TestQuestion(
            12,
            "E nas notas altas?",
            "greeting_follow_up",
            "x",
            turns=["Oi", "E nas notas altas?"],
            history_from=1,
        ),
    ]
    pipeline = RecordingPipeline()
    rows = evaluation_rows(questions, pipeline)

    assert [row["question"] for row in rows] == [
        "Quais reclamações sobre entrega?",
        "Oi",
        "E nas notas altas?",
    ]
    assert [row["turn"] for row in rows] == [1, 1, 2]
    assert pipeline.calls[1][1] == []
    history = pipeline.calls[2][1]
    assert history[0].question == "Quais reclamações sobre entrega?"
    assert history[0].answer == "Resposta para Quais reclamações sobre entrega? [1]."
    for column in MANUAL_COLUMNS:
        assert rows[0][column] == ""
