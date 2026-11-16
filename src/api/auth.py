"""Conferência da chave de acesso enviada pela página no cabeçalho X-Access-Key."""

import secrets

from fastapi import Header, HTTPException, Request

INVALID_KEY = "Chave de acesso inválida."


def require_access_key(request: Request, x_access_key: str | None = Header(default=None)) -> None:
    """Recusa com 401 a chave ausente, vazia ou errada.

    Sem chave configurada no servidor, tudo é recusado: uma configuração
    incompleta nunca deixa a API aberta. A comparação com compare_digest leva o
    mesmo tempo para qualquer chave, para que a demora da resposta não revele
    quantos caracteres estão certos.
    """
    expected = request.app.state.settings.access_key
    if not expected or not x_access_key:
        raise HTTPException(status_code=401, detail=INVALID_KEY)
    if not secrets.compare_digest(x_access_key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail=INVALID_KEY)
