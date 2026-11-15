"""Configuração do registro das etapas.

As mensagens seguem o formato "etapa=<nome> chave=valor", para facilitar a
busca nos logs do CloudWatch. Em INFO ficam as contagens e os tempos; em DEBUG,
os prompts e as respostas completas.
"""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT, force=True)
