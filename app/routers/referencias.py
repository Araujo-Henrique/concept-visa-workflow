"""Valores válidos para o front montar filtros e formulários sem duplicar regra: a fonte é o banco e os enums."""
from fastapi import APIRouter
from sqlalchemy import select

from app.deps import Sessao
from app.enums import (PERFIS, SITUACOES, Consulado, DocsREN, Monitoramento, Orientacao, Rascunho, Resultado,
                       StatusDS, TipoProcesso)
from app.models import Situacao, Usuario

router = APIRouter(prefix="/referencias", tags=["Referências"])


@router.get("")
def referencias(sessao: Sessao) -> dict:
    situacoes: dict[str, list[str]] = {t.value: [] for t in TipoProcesso}
    for s in sessao.scalars(select(Situacao)):
        situacoes[s.tipo].append(s.nome)
    ordem = {t.value: lista for t, lista in SITUACOES.items()}
    for tipo, nomes in situacoes.items():  # mantém a ordem do fluxo, não a alfabética
        nomes.sort(key=lambda n: ordem[tipo].index(n) if n in ordem[tipo] else len(ordem[tipo]))
    valores = lambda enum: [e.value for e in enum]
    return {"situacoes": situacoes, "consulados": valores(Consulado), "rascunho": valores(Rascunho),
            "status_ds": valores(StatusDS), "resultado": valores(Resultado), "orientacao": valores(Orientacao),
            "monitoramento": valores(Monitoramento), "docs_ren": valores(DocsREN), "perfis": PERFIS,
            # quem pode constar como "orientado por": usuários ativos (só id e nome, nada de e-mail)
            "usuarios": [{"id": u.id, "nome": u.nome} for u in sessao.scalars(
                select(Usuario).where(Usuario.ativo).order_by(Usuario.nome))]}
