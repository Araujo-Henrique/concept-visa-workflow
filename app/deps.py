from typing import Annotated, Iterator

from fastapi import Depends
from sqlalchemy.orm import Session as SessaoORM

from app import db


def get_sessao() -> Iterator[SessaoORM]:
    """Uma sessão (transação) por requisição. Se a rota não chamar commit, nada é gravado:
    ao sair, a sessão é fechada e o que estava pendente é desfeito."""
    with db.Session() as sessao:
        yield sessao


Sessao = Annotated[SessaoORM, Depends(get_sessao)]
