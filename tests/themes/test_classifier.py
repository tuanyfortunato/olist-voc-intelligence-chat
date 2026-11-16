import json

from src.themes.classifier import (
    SYSTEM_PROMPT,
    ReviewText,
    build_batch_message,
    classify_batch,
    classify_reviews,
    clean_themes,
    parse_batch,
)
from src.themes.taxonomy import THEMES


def reviews(n):
    return [ReviewText(f"r{i}", f"Comentário {i}") for i in range(1, n + 1)]


def test_prompt_lists_every_theme():
    for theme in THEMES:
        assert f"- {theme.id}:" in SYSTEM_PROMPT


def test_batch_message_numbers_and_cuts_long_texts():
    message = build_batch_message([ReviewText("a", "Curto"), ReviewText("b", "x" * 1000)])
    assert "[1] Curto" in message
    assert message.endswith("[2] " + "x" * 600)


def test_clean_themes_keeps_known_unique_and_at_most_three():
    assert clean_themes(["atraso", "inventado", "atraso", "defeito", "avaria", "reembolso"]) == [
        "atraso",
        "defeito",
        "avaria",
    ]
    assert clean_themes("atraso") == []


def test_parse_batch_accepts_fenced_json_and_ignores_out_of_range():
    raw = '```json\n{"1": ["atraso"], "2": [], "[3]": ["defeito"], "9": ["atraso"]}\n```'
    assert parse_batch(raw, 3) == {1: ["atraso"], 2: [], 3: ["defeito"]}


def test_parse_batch_invalid_text():
    assert parse_batch("não sei", 2) == {}
    assert parse_batch("{quebrado", 2) == {}
    assert parse_batch("[1, 2]", 2) == {}


def test_classify_batch_retries_when_answer_is_incomplete():
    answers = iter(['{"1": ["atraso"]}', '{"2": ["entrega_rapida"]}'])
    calls = []

    def call(message):
        calls.append(message)
        return next(answers), 100, 10

    result = classify_batch(reviews(2), call)
    assert len(calls) == 2
    assert result.themes == {"r1": ["atraso"], "r2": ["entrega_rapida"]}
    assert result.complete
    assert (result.input_tokens, result.output_tokens) == (200, 20)


def test_classify_batch_leaves_out_what_never_came_back():
    def call(message):
        raise RuntimeError("fora do ar")

    result = classify_batch(reviews(2), call)
    assert result.themes == {}
    assert not result.complete


def test_classify_reviews_in_batches_and_reports_each_one():
    def call(message):
        size = message.count("\n[") + 1
        return json.dumps({str(i): ["defeito"] for i in range(1, size + 1)}), 50, 5

    written = []
    result, stats = classify_reviews(reviews(45), call, workers=2, on_batch=written.append)
    assert len(result) == 45
    assert stats.batches == 3
    assert stats.failed_batches == 0
    assert stats.input_tokens == 150
    assert stats.unclassified == []
    assert sum(len(batch) for batch in written) == 45
