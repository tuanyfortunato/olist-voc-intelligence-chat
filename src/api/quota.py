"""Limite diário de perguntas, para proteger os créditos da AWS.

A contagem fica na memória da tarefa e volta a zero quando muda a data no fuso
de São Paulo. Se a tarefa reiniciar no meio do dia, a contagem também recomeça;
com uma tarefa só e desligada à noite, aceito esse limite (ver docs/07).
"""

import threading
from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def now_in_sao_paulo() -> datetime:
    return datetime.now(SAO_PAULO)


class DailyQuota:
    def __init__(self, limit: int, now: Callable[[], datetime] = now_in_sao_paulo):
        self.limit = limit
        self.now = now
        self.used = 0
        self._day: date | None = None
        # A rota é síncrona e roda em várias threads ao mesmo tempo
        self._lock = threading.Lock()

    def consume(self) -> bool:
        """Desconta uma pergunta. Devolve False quando o limite do dia já foi atingido."""
        with self._lock:
            today = self.now().astimezone(SAO_PAULO).date()
            if today != self._day:
                self._day = today
                self.used = 0
            if self.used >= self.limit:
                return False
            self.used += 1
            return True
