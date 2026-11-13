from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import Date, and_, case, func, literal, null, select, union_all

from app.deps import Sessao
from app.enums import Consulado, Orientacao, StatusDS, TipoProcesso
from app.painel import painel
from app.schemas.painel import AgendaItem, PainelOut, ResumoTipo, painel_adapter
from app.tempo import hoje_em_sp

router = APIRouter(prefix="/painel", tags=["Painel"])

SEM_DS160 = "sem"  # valor do filtro `ds160` para processos sem nenhum formulário cadastrado
MAX_DIAS_AGENDA = 92  # um trimestre: a agenda é uma janela, não um relatório do histórico inteiro

# coluna da view -> nome do evento na agenda
DATAS_DA_AGENDA = {"orientacao_data": "orientacao", "data_casv": "casv", "data_entrevista": "entrevista",
                   "data_despacho": "despacho", "data_pf": "pf", "prazo_pf": "prazo_pf"}
COLUNA_DA_DATA = {evento: coluna for coluna, evento in DATAS_DA_AGENDA.items()}
# previsão da orientação (CASV - 14): dá para filtrar o período, mas não entra na agenda (não é compromisso marcado)
COLUNA_DA_DATA["previsao_orientacao"] = "previsao_orientacao"


def proxima_data(hoje: date):
    """A data marcada mais próxima de hoje em diante (inclusive hoje); nula se não há nenhuma.

    Conta o que está AGENDADO: CASV, entrevista, orientação (só se está 'Agendada', com a data marcada), prazo do
    despacho (só se ainda não foi despachado), PF e prazo da PF. Não conta a previsão da orientação (CASV - 14): ela
    é só uma conta, não um compromisso marcado. Datas passadas não contam: já aconteceram. Processo "Concluido"
    também não sobe pela data: o que ele tinha a fazer já foi feito.
    O `least` do PostgreSQL ignora os nulos e só devolve nulo se todos forem nulos."""
    candidatas = [
        painel.c.data_casv,
        painel.c.data_entrevista,
        case((painel.c.orientacao == Orientacao.AGENDADA.value, painel.c.orientacao_data), else_=None),
        case((painel.c.despachado_em.is_(None), painel.c.data_despacho), else_=None),
        painel.c.data_pf,
        painel.c.prazo_pf,
    ]
    pendente = painel.c.situacao != "Concluido"
    return func.least(*[case((and_(c >= hoje, pendente), c), else_=None) for c in candidatas])


@router.get("", response_model=list[PainelOut])
def listar(sessao: Sessao, response: Response, tipo: TipoProcesso | None = None, situacao: str | None = None,
           consulado: Consulado | None = None, cliente: str | None = None,
           resultado_geral: str | None = None,  # Processando, Aprovado, Negado ou Parcial
           processo_id: int | None = None, cliente_id: int | None = None,
           data: Literal["orientacao", "casv", "entrevista", "despacho", "pf", "prazo_pf",
                         "previsao_orientacao"] | None = None,
           de: date | None = None, ate: date | None = None,
           despacho: Literal["pendente", "feito"] | None = None,  # REN: falta despachar / já despachado
           orientacao: Orientacao | None = None,  # OBT: em que ponto está a orientação
           ds160: str | None = None,  # status do DS-160 (o menos avançado do processo) ou "sem" (nenhum cadastrado)
           ordem: Literal["agenda", "recentes"] = "recentes",
           limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    """Visão geral dos processos, uma linha por processo (a view vw_painel_processos).
    O cabeçalho `X-Total-Count` traz o total com os mesmos filtros, para a tela paginar.
    Período: `data` diz qual data olhar (casv, entrevista...) e `de`/`ate` os limites (um deles basta).

    Ordem: `recentes` (padrão da API) traz os processos mais novos primeiro; `agenda` (a que a tela de processos
    usa) põe primeiro os que têm data marcada, da mais próxima para a mais distante (hoje em Brasília), e depois
    os demais, dos mais novos para os mais antigos. A ordem vale para todas as páginas, não só para a primeira."""
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
    if orientacao is not None:
        filtros.append(painel.c.orientacao == orientacao.value)
    if ds160 is not None:
        # o mesmo valor que a coluna mostra: o status MENOS avançado entre os DS-160 do processo
        if ds160 == SEM_DS160:
            filtros.append(painel.c.ds160_status.is_(None))
        elif ds160 in {s.value for s in StatusDS}:
            filtros.append(painel.c.ds160_status == ds160)
        else:
            validos = ", ".join([s.value for s in StatusDS] + [SEM_DS160])
            raise HTTPException(status_code=422, detail=f"DS-160 inválido. Use: {validos}")

    total = sessao.scalar(select(func.count()).select_from(painel).where(*filtros))
    response.headers["X-Total-Count"] = str(total)
    if ordem == "agenda":
        criterio = (proxima_data(hoje_em_sp()).asc().nulls_last(), painel.c.processo_id.desc())
    else:
        criterio = (painel.c.processo_id.desc(),)
    consulta = select(painel).where(*filtros).order_by(*criterio).limit(limit).offset(offset)
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
