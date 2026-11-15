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
