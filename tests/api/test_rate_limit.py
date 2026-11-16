import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from starlette.requests import Request

from src.api.rate_limit import (
    SAO_PAULO,
    MemoryCounterStore,
    PostgresCounterStore,
    QuestionLimiter,
    Window,
    client_ip,
    consume_windows,
    create_table,
    delete_old_windows,
    ip_scope,
)

from .conftest import make_client, make_limiter

QUESTION = {"question": "O que falam do frete?"}


class FakeClock:
    def __init__(self, start: datetime):
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **kwargs) -> None:
        self.current += timedelta(**kwargs)


def make_request(forwarded=None, peer="10.0.0.5"):
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def ask_from(client, ip, body=QUESTION):
    # Como a requisição chega à API: o CloudFront põe o IP de quem acessou e
    # o ALB, o do CloudFront
    return client.post("/api/ask", json=body, headers={"X-Forwarded-For": f"{ip}, 130.176.0.1"})


# --- IP de quem perguntou ---


def test_client_ip_is_the_address_added_by_cloudfront():
    assert client_ip(make_request("200.1.2.3, 130.176.0.1"), proxy_hops=2) == "200.1.2.3"


def test_client_ip_ignores_addresses_sent_by_the_client():
    # Quem acessa pode mandar o próprio X-Forwarded-For; o CloudFront só acrescenta
    request = make_request("1.1.1.1, 9.9.9.9, 200.1.2.3, 130.176.0.1")
    assert client_ip(request, proxy_hops=2) == "200.1.2.3"


def test_client_ip_without_proxies_uses_the_connection():
    assert client_ip(make_request(), proxy_hops=2) == "10.0.0.5"
    assert client_ip(make_request("130.176.0.1"), proxy_hops=2) == "10.0.0.5"
    assert client_ip(make_request("200.1.2.3"), proxy_hops=0) == "10.0.0.5"


def test_ip_scope_does_not_keep_the_ip_and_groups_ipv6_by_network():
    scope = ip_scope("200.1.2.3")
    assert "200.1.2.3" not in scope and scope.startswith("ip:")
    assert ip_scope("200.1.2.3") != ip_scope("200.1.2.4")
    assert ip_scope("2804:14c:1:2::1") == ip_scope("2804:14c:1:2:ffff::9")
    assert ip_scope("2804:14c:1:2::1") != ip_scope("2804:14c:1:3::1")


# --- Limitador ---


def test_ip_limit_resets_at_the_next_hour():
    clock = FakeClock(datetime(2026, 11, 16, 10, 25, tzinfo=SAO_PAULO))
    limiter = QuestionLimiter(2, 1000, MemoryCounterStore(), now=clock)
    assert limiter.consume("200.1.2.3") is None
    assert limiter.consume("200.1.2.3") is None
    refusal = limiter.consume("200.1.2.3")
    assert refusal.reason == "ip" and refusal.limit == 2
    assert refusal.retry_at == datetime(2026, 11, 16, 11, 0, tzinfo=SAO_PAULO)
    # Outro IP não é afetado
    assert limiter.consume("200.1.2.4") is None
    clock.advance(minutes=35)
    assert limiter.consume("200.1.2.3") is None


def test_daily_limit_counts_every_ip_and_follows_sao_paulo_time():
    clock = FakeClock(datetime(2026, 11, 16, 21, 0, tzinfo=SAO_PAULO))
    limiter = QuestionLimiter(100, 2, MemoryCounterStore(), now=clock)
    assert limiter.consume("200.1.2.3") is None
    assert limiter.consume("200.1.2.4") is None
    refusal = limiter.consume("200.1.2.5")
    assert refusal.reason == "dia"
    assert refusal.retry_at == datetime(2026, 11, 17, 0, 0, tzinfo=SAO_PAULO)
    # 01h30 em UTC ainda é 22h30 do dia 16 em São Paulo
    clock.current = datetime(2026, 11, 17, 1, 30, tzinfo=UTC)
    assert limiter.consume("200.1.2.5").reason == "dia"
    clock.current = datetime(2026, 11, 17, 9, 0, tzinfo=SAO_PAULO)
    assert limiter.consume("200.1.2.5") is None


def test_question_refused_by_the_daily_limit_does_not_use_the_ip_quota():
    store = MemoryCounterStore()
    clock = FakeClock(datetime(2026, 11, 16, 10, tzinfo=SAO_PAULO))
    limiter = QuestionLimiter(100, 1, store, now=clock)
    limiter.consume("200.1.2.3")
    assert limiter.consume("200.1.2.4").reason == "dia"
    assert sum(1 for scope, _ in store.used if scope == ip_scope("200.1.2.4")) == 0


# --- Rota ---


def test_ip_over_the_limit_gets_429_with_friendly_message(fake_pipe):
    with make_client(fake_pipe, limiter=make_limiter(hourly=2)) as client:
        for _ in range(2):
            assert ask_from(client, "200.1.2.3").status_code == 200
        response = ask_from(client, "200.1.2.3")
        assert response.status_code == 429
        assert response.json() == {
            "detail": "Você chegou ao limite de 2 perguntas por hora. "
            "Dá para voltar a perguntar a partir das 11:00, horário de Brasília."
        }
        # O relógio dos testes está em 10h25
        assert response.headers["Retry-After"] == str(35 * 60)
        assert ask_from(client, "200.1.2.4").status_code == 200
    assert fake_pipe.calls == 3


def test_daily_limit_gets_its_own_message(fake_pipe):
    with make_client(fake_pipe, limiter=make_limiter(daily=1)) as client:
        ask_from(client, "200.1.2.3")
        response = ask_from(client, "200.1.2.4")
    assert response.status_code == 429
    assert "limite de perguntas de hoje" in response.json()["detail"]


def test_invalid_body_does_not_consume_the_limit(fake_pipe):
    limiter = make_limiter(hourly=1)
    with make_client(fake_pipe, limiter=limiter) as client:
        ask_from(client, "200.1.2.3", {"question": ""})
        assert ask_from(client, "200.1.2.3").status_code == 200


def test_categories_do_not_consume_the_limit(fake_pipe):
    with make_client(fake_pipe, limiter=make_limiter(hourly=1)) as client:
        for _ in range(3):
            assert client.get("/api/categories").status_code == 200
        assert ask_from(client, "200.1.2.3").status_code == 200


def test_database_error_in_the_limit_is_503(fake_pipe):
    import psycopg

    class BrokenStore:
        def consume(self, windows):
            raise psycopg.OperationalError("sem conexão")

    limiter = QuestionLimiter(100, 1000, BrokenStore())
    with make_client(fake_pipe, limiter=limiter) as client:
        response = client.post("/api/ask", json=QUESTION)
    assert response.status_code == 503 and fake_pipe.calls == 0
    assert "sem conexão" not in response.text


# --- Contagem no PostgreSQL ---


@pytest.fixture
def counts_conn():
    """Schema próprio no PostgreSQL de teste, só com a tabela da contagem."""
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("sem TEST_DATABASE_URL")
    import psycopg

    schema = f"teste_{uuid.uuid4().hex[:8]}"
    admin = psycopg.connect(url, autocommit=True)
    admin.execute(f"CREATE SCHEMA {schema}")

    def connect():
        return psycopg.connect(url, options=f"-c search_path={schema}")

    with connect() as conn:
        create_table(conn)
    yield connect
    admin.execute(f"DROP SCHEMA {schema} CASCADE")
    admin.close()


HOUR = datetime(2026, 11, 16, 10, 0, tzinfo=SAO_PAULO)


def test_postgres_store_stops_at_the_limit(counts_conn):
    store = PostgresCounterStore(counts_conn)
    window = Window("ip:abc", HOUR, 2)
    assert store.consume([window]) is None
    assert store.consume([window]) is None
    assert store.consume([window]) == 0
    with counts_conn() as conn:
        assert conn.execute("SELECT used FROM question_counts").fetchone()[0] == 2


def test_postgres_store_undoes_the_ip_count_when_the_day_refuses(counts_conn):
    store = PostgresCounterStore(counts_conn)
    day = Window("dia", HOUR.replace(hour=0), 1)
    assert store.consume([Window("ip:a", HOUR, 100), day]) is None
    assert store.consume([Window("ip:b", HOUR, 100), day]) == 1
    with counts_conn() as conn:
        rows = conn.execute("SELECT scope FROM question_counts ORDER BY scope").fetchall()
    scopes = [row[0] for row in rows]
    assert scopes == ["dia", "ip:a"]


def test_postgres_store_is_shared_between_connections(counts_conn):
    # Duas tarefas do ECS são duas conexões diferentes com o mesmo banco
    window = Window("ip:abc", HOUR, 3)
    first, second = counts_conn(), counts_conn()
    try:
        assert consume_windows(first, [window]) is None
        assert consume_windows(second, [window]) is None
        assert consume_windows(first, [window]) is None
        assert consume_windows(second, [window]) == 0
    finally:
        first.close()
        second.close()


def test_old_windows_are_deleted(counts_conn):
    store = PostgresCounterStore(counts_conn)
    store.consume([Window("ip:a", HOUR - timedelta(days=3), 10)])
    store.consume([Window("ip:a", HOUR, 10)])
    with counts_conn() as conn:
        delete_old_windows(conn, HOUR - timedelta(days=2))
        conn.commit()
        assert conn.execute("SELECT count(*) FROM question_counts").fetchone()[0] == 1
