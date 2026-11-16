"""Limite de perguntas por IP e teto diário do chat.

O chat é aberto, sem chave de acesso. Para que uma pessoa sozinha não esgote
os créditos da AWS, cada IP pode fazer um número limitado de perguntas por
hora, e o chat inteiro tem um teto por dia. As duas contagens usam janelas
fixas, a hora cheia e o dia no fuso de São Paulo, o que deixa a página dizer
com exatidão quando a pessoa pode voltar a perguntar.

A contagem fica no PostgreSQL, que a API já usa para a busca. Assim ela vale
para todas as tarefas do ECS ao mesmo tempo e não recomeça quando uma tarefa
reinicia. O IP não é gravado: a tabela guarda só um resumo SHA-256 dele.
"""

import hashlib
import ipaddress
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

import psycopg
from fastapi import Request

from src.config import Settings

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
DAILY_SCOPE = "dia"

# Janelas mais antigas que isso já não contam e são apagadas quando a API sobe
KEEP_WINDOWS = timedelta(days=2)


def now_in_sao_paulo() -> datetime:
    return datetime.now(SAO_PAULO)


def client_ip(request: Request, proxy_hops: int) -> str:
    """IP de quem fez a pergunta.

    Na AWS, a requisição passa pelo CloudFront e pelo ALB, e cada um acrescenta
    um endereço no fim do X-Forwarded-For: o CloudFront, o IP de quem acessou a
    página, e o ALB, o IP do CloudFront. O valor certo é, portanto, o que está
    proxy_hops posições antes do fim. Os endereços mais à esquerda vêm de quem
    fez a requisição e podem ser inventados, por isso nunca são usados. Sem o
    cabeçalho, como ao rodar a API no computador, vale o IP da conexão.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    hops = [part.strip() for part in forwarded.split(",") if part.strip()]
    if proxy_hops > 0 and len(hops) >= proxy_hops:
        return hops[-proxy_hops]
    return request.client.host if request.client else "desconhecido"


def ip_scope(ip: str) -> str:
    """Chave da contagem de um IP, sem o IP em claro.

    Um endereço IPv6 conta pela rede /64, porque quem tem um costuma ter a rede
    inteira e poderia trocar de endereço a cada pergunta.
    """
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        key = ip
    else:
        if address.version == 6:
            key = str(ipaddress.ip_network(f"{address}/64", strict=False))
        else:
            key = str(address)
    return "ip:" + hashlib.sha256(key.encode()).hexdigest()[:32]


@dataclass(frozen=True)
class Window:
    scope: str
    start: datetime
    limit: int


@dataclass(frozen=True)
class Refusal:
    """Pergunta recusada: qual limite foi atingido e quando ele volta a zero."""

    reason: str  # "ip" ou "dia"
    limit: int
    retry_at: datetime


class CounterStore(Protocol):
    def consume(self, windows: list[Window]) -> int | None:
        """Desconta uma pergunta de todas as janelas, ou de nenhuma.

        Devolve a posição da primeira janela que já estava no limite, ou None
        quando a pergunta foi contada em todas.
        """


class PostgresCounterStore:
    """Contagem no PostgreSQL, compartilhada por todas as tarefas."""

    def __init__(self, connect: Callable[[], psycopg.Connection]):
        self.connect = connect

    def ensure_table(self) -> None:
        with self.connect() as conn:
            create_table(conn)
            delete_old_windows(conn, now_in_sao_paulo() - KEEP_WINDOWS)
            conn.commit()

    def consume(self, windows: list[Window]) -> int | None:
        with self.connect() as conn:
            return consume_windows(conn, windows)


def create_table(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS question_counts (
            scope text NOT NULL,
            window_start timestamptz NOT NULL,
            used int NOT NULL,
            PRIMARY KEY (scope, window_start)
        )
        """
    )


def delete_old_windows(conn: psycopg.Connection, before: datetime) -> None:
    conn.execute("DELETE FROM question_counts WHERE window_start < %s", (before,))


def consume_windows(conn: psycopg.Connection, windows: list[Window]) -> int | None:
    """Desconta uma pergunta de cada janela numa transação só.

    O INSERT ... ON CONFLICT trava a linha da janela, e o WHERE só deixa somar
    enquanto ela está abaixo do limite. Duas tarefas que recebem perguntas do
    mesmo IP ao mesmo tempo esperam uma pela outra, e a contagem nunca passa do
    limite. Se uma janela recusar, o rollback desfaz o que já tinha sido somado
    nas anteriores: uma pergunta recusada pelo teto do dia não gasta a cota do IP.
    """
    refused = None
    with conn.transaction():
        for position, window in enumerate(windows):
            row = conn.execute(
                """
                INSERT INTO question_counts (scope, window_start, used)
                VALUES (%s, %s, 1)
                ON CONFLICT (scope, window_start) DO UPDATE
                SET used = question_counts.used + 1
                WHERE question_counts.used < %s
                RETURNING used
                """,
                (window.scope, window.start, window.limit),
            ).fetchone()
            if row is None:
                refused = position
                raise psycopg.Rollback()
    return refused


class MemoryCounterStore:
    """Contagem na memória, para os testes da API e para rodar sem banco."""

    def __init__(self):
        self.used: dict[tuple[str, datetime], int] = {}
        self._lock = threading.Lock()

    def consume(self, windows: list[Window]) -> int | None:
        with self._lock:
            for position, window in enumerate(windows):
                if self.used.get((window.scope, window.start), 0) >= window.limit:
                    return position
            for window in windows:
                key = (window.scope, window.start)
                self.used[key] = self.used.get(key, 0) + 1
            return None


class QuestionLimiter:
    def __init__(
        self,
        hourly_per_ip: int,
        daily_total: int,
        store: CounterStore,
        now: Callable[[], datetime] = now_in_sao_paulo,
    ):
        self.hourly_per_ip = hourly_per_ip
        self.daily_total = daily_total
        self.store = store
        self.now = now

    def consume(self, ip: str) -> Refusal | None:
        """Desconta uma pergunta do IP e do dia. Devolve a recusa, se houver."""
        now = self.now().astimezone(SAO_PAULO)
        hour = now.replace(minute=0, second=0, microsecond=0)
        day = hour.replace(hour=0)
        refused = self.store.consume(
            [
                Window(ip_scope(ip), hour, self.hourly_per_ip),
                Window(DAILY_SCOPE, day, self.daily_total),
            ]
        )
        if refused == 0:
            return Refusal("ip", self.hourly_per_ip, hour + timedelta(hours=1))
        if refused == 1:
            return Refusal("dia", self.daily_total, day + timedelta(days=1))
        return None


def refusal_message(refusal: Refusal) -> str:
    if refusal.reason == "ip":
        hour = refusal.retry_at.astimezone(SAO_PAULO).strftime("%H:%M")
        return (
            f"Você chegou ao limite de {refusal.limit} perguntas por hora. "
            f"Dá para voltar a perguntar a partir das {hour}, horário de Brasília."
        )
    return "O chat chegou ao limite de perguntas de hoje. Volte amanhã para continuar."


def build_limiter(settings: Settings) -> QuestionLimiter:
    from src.vector_db import connect

    store = PostgresCounterStore(lambda: connect(settings, register=False))
    store.ensure_table()
    return QuestionLimiter(
        settings.hourly_question_limit_per_ip, settings.daily_question_limit, store
    )
