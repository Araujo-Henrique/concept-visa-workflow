from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import Date, func, literal, null, select, union_all

from app.deps import Sessao
from app.enums import Consulado, TipoProcesso
from app.painel import painel
from app.schemas.painel import AgendaItem, PainelOut, ResumoTipo, painel_adapter

router = APIRouter(prefix="/painel", tags=["Painel"])

MAX_DIAS_AGENDA = 92  # um trimestre: a agenda é uma janela, não um relatório do histórico inteiro

# coluna da view -> nome do evento na agenda
DATAS_DA_AGENDA = {"orientacao_data": "orientacao", "data_casv": "casv", "data_entrevista": "entrevista",
                   "data_despacho": "despacho", "data_pf": "pf", "prazo_pf": "prazo_pf"}
COLUNA_DA_DATA = {evento: coluna for coluna, evento in DATAS_DA_AGENDA.items()}


@router.get("", response_model=list[PainelOut])
def listar(sessao: Sessao, response: Response, tipo: TipoProcesso | None = None, situacao: str | None = None,
           consulado: Consulado | None = None, cliente: str | None = None,
           resultado_geral: str | None = None,  # Processando, Aprovado, Negado ou Parcial
           processo_id: int | None = None, cliente_id: int | None = None,
           data: Literal["orientacao", "casv", "entrevista", "despacho", "pf", "prazo_pf"] | None = None,
           de: date | None = None, ate: date | None = None,
           despacho: Literal["pendente", "feito"] | None = None,  # REN: falta despachar / já despachado
           limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    """Visão geral dos processos, uma linha por processo (a view vw_painel_processos).
    O cabeçalho `X-Total-Count` traz o total com os mesmos filtros, para a tela paginar.
    Período: `data` diz qual data olhar (casv, entrevista...) e `de`/`ate` os limites (um deles basta)."""
    filtros = []
    if (de or ate) and data is None:
        raise HTTPException(status_code=422, detail="Informe qual data o período filtra (parâmetro `data`)")
    if de and ate and ate < de:
        raise HTTPException(status_code=422, detail="O fim do período vem antes do início")
    if data is not None:
        coluna = painel.c[COLUNA_DA_DATA[data]]
        if de:
            filtros.append(coluna >= de)
        if ate:
            filtros.append(coluna <= ate)
    if tipo is not None:
        filtros.append(painel.c.tipo == tipo.value)
    if situacao:
        filtros.append(painel.c.situacao == situacao)
    if consulado is not None:
        filtros.append(painel.c.consulado == consulado.value)
    if cliente:
        filtros.append(func.strpos(func.lower(painel.c.cliente), cliente.lower()) > 0)
    if resultado_geral:
        filtros.append(painel.c.resultado_geral == resultado_geral)
    if processo_id is not None:
        filtros.append(painel.c.processo_id == processo_id)
    if cliente_id is not None:
        filtros.append(painel.c.cliente_id == cliente_id)
    if despacho == "pendente":
        filtros += [painel.c.despachado_em.is_(None), painel.c.data_despacho.is_not(None)]
    elif despacho == "feito":
        filtros.append(painel.c.despachado_em.is_not(None))

    total = sessao.scalar(select(func.count()).select_from(painel).where(*filtros))
    response.headers["X-Total-Count"] = str(total)
    consulta = select(painel).where(*filtros).order_by(painel.c.processo_id.desc()).limit(limit).offset(offset)
    # o discriminador `tipo` escolhe o schema de cada linha e descarta as colunas que não pertencem ao tipo
    return [painel_adapter.validate_python(dict(linha._mapping)) for linha in sessao.execute(consulta)]


@router.get("/resumo", response_model=dict[TipoProcesso, ResumoTipo])
def resumo(sessao: Sessao):
    """Contagens para o início: por tipo, situação e resultado (agregado no banco, não em Python)."""
    saida = {t.value: {"total": 0, "por_situacao": {}, "por_resultado": {}} for t in TipoProcesso}
    for coluna, chave in ((painel.c.situacao, "por_situacao"), (painel.c.resultado_geral, "por_resultado")):
        for tipo, valor, n in sessao.execute(
                select(painel.c.tipo, coluna, func.count()).group_by(painel.c.tipo, coluna)):
            saida[tipo][chave][valor] = n
    for tipo, n in sessao.execute(select(painel.c.tipo, func.count()).group_by(painel.c.tipo)):
        saida[tipo]["total"] = n
    return saida


@router.get("/agenda", response_model=list[AgendaItem])
def agenda(sessao: Sessao, de: date, ate: date):
    """Toda data marcada no período (orientação, CASV, entrevista, despacho, PF), em ordem."""
    if ate < de:
        raise HTTPException(status_code=422, detail="O fim do período vem antes do início")
    if (ate - de).days > MAX_DIAS_AGENDA:
        raise HTTPException(status_code=422, detail=f"Período máximo: {MAX_DIAS_AGENDA} dias")
    partes = [
        select(painel.c[coluna].label("data"), literal(evento).label("evento"), painel.c.processo_id,
               painel.c.tipo, painel.c.cliente, painel.c.situacao, painel.c.consulado,
               # só o despacho tem "feito": os outros eventos levam nulo
               (painel.c.despachado_em if evento == "despacho" else null().cast(Date)).label("despachado_em"))
        .where(painel.c[coluna].between(de, ate))
        for coluna, evento in DATAS_DA_AGENDA.items()]
    uniao = union_all(*partes).subquery()
    consulta = select(uniao).order_by(uniao.c.data, uniao.c.evento, uniao.c.processo_id)
    return [dict(linha._mapping) for linha in sessao.execute(consulta)]
