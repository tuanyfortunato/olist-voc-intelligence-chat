from datetime import UTC, datetime

from src.themes.dashboard import ReviewRow, build_dashboard, pick_examples, review_sample, summarize


def row(review_id, rating, delivery="no_prazo", date="2018-03-10", themes=(), text=None):
    return ReviewRow(
        review_id=review_id,
        rating=rating,
        delivery=delivery,
        category="bebes",
        review_date=date,
        original_text=text or f"Comentário de teste número {review_id}, longo o bastante.",
        themes=tuple(themes),
    )


ROWS = [
    row("a", 1, "atrasada", "2017-12-02", ["atraso", "sem_resposta"]),
    row("b", 2, "nao_entregue", "2018-03-01", ["nao_recebido"]),
    row("c", 5, "no_prazo", "2018-03-05", ["entrega_rapida"]),
    row("d", 4, "no_prazo", "2018-04-01", ["atraso"]),
    row("e", 5, "no_prazo", "2016-10-01"),
]


def test_summarize_ratings_delivery_and_themes():
    summary = summarize(ROWS)
    assert summary["total"] == 5
    assert summary["avg_rating"] == 3.4
    assert summary["ratings"] == {"1": 1, "2": 1, "3": 0, "4": 1, "5": 2}
    assert summary["delivery"]["atrasada"] == {"count": 1, "avg_rating": 1.0}
    assert summary["delivery"]["no_prazo"]["avg_rating"] == 4.67
    assert summary["themes"]["atraso"] == {"count": 2, "avg_rating": 2.5, "low": 1}
    assert summary["themes"]["defeito"] == {"count": 0, "avg_rating": None, "low": 0}
    # "a" tem dois temas de setores diferentes e conta uma vez em cada setor
    assert summary["sectors"]["logistica"] == {"count": 3, "avg_rating": 2.33, "low": 2}
    assert summary["sectors"]["vendedor"] == {"count": 1, "avg_rating": 1.0, "low": 1}
    assert summary["sectors"]["produto"]["count"] == 0


def test_summarize_monthly_counts_low_and_late():
    monthly = {item["month"]: item for item in summarize(ROWS)["monthly"]}
    assert monthly["2018-03"] == {"month": "2018-03", "total": 2, "low": 1, "high": 1, "late": 1}
    assert list(monthly) == sorted(monthly)


def test_dashboard_periods_and_metadata():
    data = build_dashboard(ROWS, "modelo", now=datetime(2026, 11, 16, tzinfo=UTC))
    assert data["generated_at"] == "2026-11-16T00:00:00+00:00"
    assert data["total"] == 5
    assert data["classified"] == 4
    assert data["periods"]["todos"]["total"] == 5
    assert data["periods"]["2018"]["total"] == 3
    assert data["periods"]["2017"]["total"] == 1
    assert {sector["id"] for sector in data["sectors"]} >= {"logistica", "fortes"}
    assert data["themes"][0].keys() == {"id", "label", "sector", "polarity"}


def test_examples_match_polarity_and_prefer_single_theme():
    examples = pick_examples(ROWS)
    # "a" (nota 1) entra em atraso; "d" tem nota 4 e não serve de exemplo de reclamação
    assert [item["review_id"] for item in examples["atraso"]] == ["a"]
    assert [item["review_id"] for item in examples["entrega_rapida"]] == ["c"]
    assert examples["defeito"] == []


def test_examples_skip_texts_too_short_or_too_long():
    rows = [
        row("x", 1, themes=["defeito"], text="Ruim"),
        row("y", 1, themes=["defeito"], text="z" * 400),
    ]
    assert pick_examples(rows)["defeito"] == []


def test_review_sample_is_fixed_and_has_empty_review_columns():
    first = review_sample(ROWS, size=3)
    assert first == review_sample(ROWS, size=3)
    assert len(first) == 3
    assert first[0]["temas_corretos"] == ""
