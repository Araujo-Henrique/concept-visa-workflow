"""Auditoria: quem mudou o quê, com antes e depois. O registro em si é feito pelo banco (trigger da
migration 0011); aqui a API só conta ao banco QUEM está mexendo, no começo de cada transação.

Por que no começo de cada transação: `set_config(..., true)` vale só até o commit (como um SET LOCAL). Assim
o valor nunca vaza para outra requisição que reaproveite a mesma conexão do pool. Se a rota fizer commit e
continuar gravando, a nova transação recebe os mesmos valores (evento `after_begin`).

Origens: `api` (pela tela/API, com usuário), `seed`, `importacao` (scripts) e `banco` (qualquer coisa feita
fora da aplicação, como um UPDATE manual no psql: fica registrada, sem usuário).
"""
from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app import db, logs

_CHAVE = "auditoria"


def identificar(sessao: Session, *, usuario_id: int | None = None, origem: str = "api") -> None:
    """Marca a sessão: o que ela gravar daqui em diante sai na auditoria com este usuário e esta origem."""
    sessao.info[_CHAVE] = {"usuario_id": usuario_id, "origem": origem}
    if sessao.in_transaction():  # a transação já começou (ex.: a consulta que achou o usuário)
        _aplicar(sessao.connection(), sessao.info[_CHAVE])


def _aplicar(conexao: Connection, dados: dict) -> None:
    requisicao = logs.id_da_requisicao.get()
    conexao.execute(
        text("SELECT set_config('app.usuario_id', :usuario, true), set_config('app.requisicao', :requisicao, true),"
             " set_config('app.origem', :origem, true)"),
        {"usuario": "" if dados["usuario_id"] is None else str(dados["usuario_id"]),
         "requisicao": "" if requisicao == "-" else requisicao,
         "origem": dados["origem"]})


@event.listens_for(db.Session, "after_begin")
def _ao_comecar_transacao(sessao: Session, _transacao, conexao: Connection) -> None:
    if dados := sessao.info.get(_CHAVE):
        _aplicar(conexao, dados)
