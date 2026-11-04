from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.deps import Sessao
from app.enums import Consulado, TipoProcesso
from app.painel import painel
from app.schemas.painel import PainelOut

router = APIRouter(prefix="/painel", tags=["Painel"])


@router.get("", response_model=list[PainelOut])
def listar(sessao: Sessao, tipo: TipoProcesso | None = None, situacao: str | None = None,
           consulado: Consulado | None = None, cliente: str | None = None,
           resultado_geral: str | None = None,  # Processando, Aprovado, Negado ou Parcial
           limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    """Visão geral dos processos, uma linha por processo (a view vw_painel_processos)."""
    consulta = select(painel).order_by(painel.c.processo_id.desc()).limit(limit).offset(offset)
    if tipo is not None:
        consulta = consulta.where(painel.c.tipo == tipo.value)
    if situacao:
        consulta = consulta.where(painel.c.situacao == situacao)
    if consulado is not None:
        consulta = consulta.where(painel.c.consulado == consulado.value)
    if cliente:
        consulta = consulta.where(func.strpos(func.lower(painel.c.cliente), cliente.lower()) > 0)
    if resultado_geral:
        consulta = consulta.where(painel.c.resultado_geral == resultado_geral)
    return [PainelOut(**linha._mapping) for linha in sessao.execute(consulta)]
