import json

from scripts.run_ragas import clean_answer, ragas_rows, ragas_sample, status_check, summary_rows
from src.rag.prompts import PREMISE_NOTE


def make_row(**values):
    row = {
        "question_id": "1",
        "turn": "1",
        "question": "O que falam da entrega?",
        "filters": "sem filtro",
        "type": "with_evidence",
        "status": "answered",
        "answer": "Atrasos [1][2] e extravios [3].",
        "retrieved_json": json.dumps(
            [
                {"number": 2, "original_text": "Chegou depois do prazo"},
                {"number": 1, "original_text": "Atrasou uma semana"},
            ]
        ),
    }
    row.update(values)
    return row


def test_clean_answer_removes_citations_and_premise_note():
    answer = f"Atrasos [1][2] e extravios [3].\n\n{PREMISE_NOTE}"
    assert clean_answer(answer) == "Atrasos e extravios."


def test_sample_keeps_search_order():
    sample = ragas_sample(make_row())
    assert sample["user_input"] == "O que falam da entrega?"
    assert sample["response"] == "Atrasos e extravios."
    assert sample["retrieved_contexts"] == ["Atrasou uma semana", "Chegou depois do prazo"]


def test_refusals_and_fixed_messages_are_not_scored():
    for status in ["out_of_scope", "greeting", "no_evidence"]:
        assert ragas_sample(make_row(status=status)) is None
    assert ragas_sample(make_row(retrieved_json="[]")) is None


def test_status_check():
    assert status_check(make_row()) == "sim"
    assert status_check(make_row(type="no_evidence", status="weak_evidence")) == "não"
    assert status_check(make_row(type="out_of_scope", status="out_of_scope")) == "sim"
    assert status_check(make_row(type="greeting_follow_up", status="greeting")) == "sim"
    assert status_check(make_row(type="greeting_follow_up", turn="2", status="out_of_scope")) == (
        "não"
    )
    # A mudança de regra fica para a revisão manual
    assert status_check(make_row(type="rule_change", status="out_of_scope")) == ""


def test_ragas_rows_match_scores_to_scored_rows():
    rows = [
        make_row(question_id="1"),
        make_row(question_id="6", type="out_of_scope", status="out_of_scope"),
        make_row(question_id="5", type="weak_evidence", status="weak_evidence"),
    ]
    calls = []

    def scorer(samples):
        calls.append(samples)
        return [
            {"faithfulness": 1.0, "answer_relevancy": 0.81234, "context_precision": 0.5},
            {"faithfulness": float("nan"), "answer_relevancy": 0.4, "context_precision": 0.2},
        ]

    result = ragas_rows(rows, scorer)
    assert len(calls[0]) == 2
    assert [r["avaliada_ragas"] for r in result] == ["sim", "não", "sim"]
    assert result[0]["answer_relevancy"] == "0.812"
    assert result[1]["faithfulness"] == "" and result[1]["situacao_esperada"] == "sim"
    assert result[2]["faithfulness"] == "" and result[2]["context_precision"] == "0.200"


def test_no_scorer_call_when_nothing_to_score():
    rows = [make_row(type="out_of_scope", status="out_of_scope")]

    def scorer(samples):
        raise AssertionError("não deveria chamar o juiz")

    assert ragas_rows(rows, scorer)[0]["avaliada_ragas"] == "não"


def test_summary_by_type_and_total():
    rows = ragas_rows(
        [make_row(), make_row(question_id="2"), make_row(type="out_of_scope", status="answered")],
        lambda samples: [
            {"faithfulness": 1.0, "answer_relevancy": 0.8, "context_precision": 0.6}
            for _ in samples
        ],
    )
    summary = {line["tipo"]: line for line in summary_rows(rows)}
    assert summary["with_evidence"]["faithfulness"] == "1.000"
    assert summary["with_evidence"]["situacao_esperada"] == "2 de 2"
    assert summary["out_of_scope"]["situacao_esperada"] == "0 de 1"
    assert summary["total"]["linhas"] == 3 and summary["total"]["avaliadas_ragas"] == 3


def test_markdown_report_lists_scores_and_answers():
    from scripts.run_ragas import markdown_report

    source = [make_row()]
    rows = ragas_rows(
        source,
        lambda samples: [{"faithfulness": 1.0, "answer_relevancy": 0.8, "context_precision": 0.6}],
    )
    answers = {(r["question_id"], r["turn"], r["filters"]): r["answer"] for r in source}
    report = markdown_report(rows, summary_rows(rows), answers)
    assert "| with_evidence | 1 | 1 | 1 de 1 | 1.000 | 0.800 | 0.600 |" in report
    assert "Atrasos [1][2] e extravios [3]." in report
