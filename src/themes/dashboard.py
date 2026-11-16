"""Números do painel, calculados a partir das avaliações já classificadas.

O resultado é um JSON pequeno e estático, publicado junto com a página. O
painel não consulta a API: abre rápido, funciona fora do horário do chat e não
gasta a cota de perguntas.

Os indicadores de nota e de entrega vêm dos metadados das avaliações; as
contagens por tema, da classificação em lote. Os comentários de exemplo de cada
tema são escolhidos de forma determinística, para o JSON não mudar entre duas
execuções sobre os mesmos dados.
"""

import hashlib
import random
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from src.themes.taxonomy import SECTORS, THEMES, THEMES_BY_ID, themes_of_sector

LATE = ("atrasada", "nao_entregue")
DELIVERIES = ("no_prazo", "atrasada", "nao_entregue")
PERIODS = {"todos": "Todo o período", "2018": "2018", "2017": "2017"}
EXAMPLES_PER_THEME = 3
EXAMPLE_MIN_CHARS = 40
EXAMPLE_MAX_CHARS = 180
TOP_CATEGORIES = 10
SAMPLE_SIZE = 150


@dataclass(frozen=True)
class ReviewRow:
    review_id: str
    rating: int
    delivery: str
    category: str
    review_date: str
    original_text: str
    themes: tuple[str, ...] = ()


def _average(total: int, count: int) -> float | None:
    return round(total / count, 2) if count else None


def summarize(rows: Sequence[ReviewRow]) -> dict:
    """Indicadores de um conjunto de avaliações: notas, entrega, temas, meses e categorias."""
    total = len(rows)
    ratings = Counter(row.rating for row in rows)
    delivery: dict[str, dict] = {}
    for status in DELIVERIES:
        subset = [row.rating for row in rows if row.delivery == status]
        delivery[status] = {"count": len(subset), "avg_rating": _average(sum(subset), len(subset))}

    by_theme: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        for theme in row.themes:
            by_theme[theme].append(row.rating)
    themes = {
        theme.id: {
            "count": len(by_theme[theme.id]),
            "avg_rating": _average(sum(by_theme[theme.id]), len(by_theme[theme.id])),
            "low": sum(rating <= 2 for rating in by_theme[theme.id]),
        }
        for theme in THEMES
    }

    months: dict[str, list[ReviewRow]] = defaultdict(list)
    for row in rows:
        months[row.review_date[:7]].append(row)
    monthly = [
        {
            "month": month,
            "total": len(items),
            "low": sum(item.rating <= 2 for item in items),
            "late": sum(item.delivery in LATE for item in items),
        }
        for month, items in sorted(months.items())
    ]

    categories: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        categories[row.category].append(row.rating)
    top = sorted(categories.items(), key=lambda item: (-len(item[1]), item[0]))[:TOP_CATEGORIES]

    return {
        "total": total,
        "avg_rating": _average(sum(row.rating for row in rows), total),
        "ratings": {str(rating): ratings.get(rating, 0) for rating in range(1, 6)},
        "delivery": delivery,
        "themes": themes,
        "monthly": monthly,
        "categories": [
            {
                "category": name,
                "count": len(values),
                "avg_rating": _average(sum(values), len(values)),
                "low": sum(rating <= 2 for rating in values),
            }
            for name, values in top
        ],
    }


def _stable_key(review_id: str) -> str:
    return hashlib.sha256(review_id.encode()).hexdigest()


def pick_examples(rows: Iterable[ReviewRow], per_theme: int = EXAMPLES_PER_THEME) -> dict:
    """Comentários curtos de cada tema, com nota coerente com ele: 1 ou 2 nas
    reclamações, 4 ou 5 nos elogios. Os que têm só aquele tema vêm primeiro."""
    candidates: dict[str, list[ReviewRow]] = defaultdict(list)
    for row in rows:
        if not EXAMPLE_MIN_CHARS <= len(row.original_text) <= EXAMPLE_MAX_CHARS:
            continue
        for theme_id in row.themes:
            polarity = THEMES_BY_ID[theme_id].polarity
            if (polarity == "reclamacao" and row.rating <= 2) or (
                polarity == "elogio" and row.rating >= 4
            ):
                candidates[theme_id].append(row)
    examples = {}
    for theme in THEMES:
        chosen = sorted(
            candidates[theme.id], key=lambda row: (len(row.themes), _stable_key(row.review_id))
        )
        examples[theme.id] = [
            {
                "review_id": row.review_id,
                "rating": row.rating,
                "delivery": row.delivery,
                "category": row.category,
                "review_date": row.review_date,
                "text": row.original_text,
            }
            for row in chosen[:per_theme]
        ]
    return examples


def build_dashboard(rows: Sequence[ReviewRow], model_id: str, now: datetime | None = None) -> dict:
    periods = {}
    for key, label in PERIODS.items():
        subset = rows if key == "todos" else [row for row in rows if row.review_date[:4] == key]
        periods[key] = {"label": label, **summarize(subset)}
    return {
        "generated_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "model_id": model_id,
        "total": len(rows),
        "classified": sum(bool(row.themes) for row in rows),
        "sectors": [
            {
                "id": sector.id,
                "label": sector.label,
                "summary": sector.summary,
                "themes": themes_of_sector(sector.id),
            }
            for sector in SECTORS
        ],
        "themes": [
            {
                "id": theme.id,
                "label": theme.label,
                "sector": theme.sector,
                "polarity": theme.polarity,
            }
            for theme in THEMES
        ],
        "periods": periods,
        "examples": pick_examples(rows),
    }


def review_sample(rows: Sequence[ReviewRow], size: int = SAMPLE_SIZE, seed: int = 42) -> list[dict]:
    """Amostra fixa para conferir a classificação à mão, com as colunas da revisão vazias."""
    chosen = random.Random(seed).sample(list(rows), min(size, len(rows)))
    return [
        {
            "review_id": row.review_id,
            "rating": row.rating,
            "text": row.original_text,
            "themes": ";".join(row.themes),
            "temas_corretos": "",
            "temas_faltando": "",
            "observacao": "",
        }
        for row in chosen
    ]
