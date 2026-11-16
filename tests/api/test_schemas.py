from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from src.api.quota import SAO_PAULO, DailyQuota
from src.api.schemas import AskRequest


class FakeClock:
    def __init__(self, start: datetime):
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **delta):
        self.current += timedelta(**delta)


def test_question_limits():
    assert AskRequest(question="  O que falam do frete?  ").question == "O que falam do frete?"
    AskRequest(question="a" * 500)
    for bad in ["", "   ", "a" * 501]:
        with pytest.raises(ValidationError):
            AskRequest(question=bad)


def test_history_limits():
    turn = {"question": "q", "answer": "x" * 3000}
    assert len(AskRequest(question="q", history=[turn]).history[0].answer) == 1500
    AskRequest(question="q", history=[turn] * 3)
    with pytest.raises(ValidationError):
        AskRequest(question="q", history=[turn] * 4)


def test_filters_are_accepted_and_validated():
    request = AskRequest(
        question="q", filters={"ratings": [1, 2], "category": "bebes", "delivery": "atrasada"}
    )
    assert request.filters.ratings == [1, 2]
    with pytest.raises(ValidationError):
        AskRequest(question="q", filters={"ratings": [6]})
    with pytest.raises(ValidationError):
        AskRequest(question="q", filters={"delivery": "extraviada"})


def test_quota_resets_next_day():
    clock = FakeClock(datetime(2026, 11, 16, 23, 0, tzinfo=SAO_PAULO))
    quota = DailyQuota(limit=2, now=clock)
    assert quota.consume() and quota.consume() and not quota.consume()
    assert quota.used == 2
    clock.advance(hours=2)
    assert quota.consume()
    assert quota.used == 1


def test_quota_day_follows_sao_paulo_time():
    # 01h30 em UTC ainda é 22h30 do dia anterior em São Paulo: mesma cota
    clock = FakeClock(datetime(2026, 11, 16, 23, 0, tzinfo=SAO_PAULO))
    quota = DailyQuota(limit=1, now=clock)
    assert quota.consume()
    clock.current = datetime(2026, 11, 17, 1, 30, tzinfo=UTC)
    assert not quota.consume()
