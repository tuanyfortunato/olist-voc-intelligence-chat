from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.rate_limit import SAO_PAULO, MemoryCounterStore, QuestionLimiter
from src.config import Settings
from src.rag.schemas import AskResult, RetrievedReview
from src.vector_db import IndexStatus
from src.vector_store import IndexManifest

MANIFEST = IndexManifest(
    "cohere.embed-multilingual-v3", 1024, "cosine", "2026-11-15T20:49:11Z", 40521, ["bebes"]
)


def fixed_clock():
    return datetime(2026, 11, 16, 10, 25, tzinfo=SAO_PAULO)


def make_limiter(hourly=100, daily=1000):
    return QuestionLimiter(hourly, daily, MemoryCounterStore(), now=fixed_clock)


def review(review_id, number):
    return RetrievedReview(
        review_id, 1, "bebes", "atrasada", "2018-03-10", f"Texto {review_id}", 0.7, number
    )


class FakePipeline:
    """Pipeline sem AWS: devolve sempre a mesma resposta ou levanta o erro pedido."""

    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls = 0
        self.received = []

    def ask(self, question, history=None, filters=None):
        self.calls += 1
        self.received.append((question, history))
        self.filters = filters
        if self.error:
            raise self.error
        return AskResult(
            status="answered",
            answer="Os clientes reclamam de atraso [1].",
            cited=[review("r1", 1)],
            uncited=[review("r2", 2)],
            original_question=question,
            search_topic="reclamações sobre entrega",
        )


def make_client(pipeline, limiter=None):
    app = create_app(
        Settings(),
        status_provider=lambda: IndexStatus(MANIFEST, 40521),
        pipeline=pipeline,
        limiter=limiter or make_limiter(),
    )
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def fake_pipe():
    return FakePipeline()


@pytest.fixture
def client(fake_pipe):
    with make_client(fake_pipe) as test_client:
        yield test_client
