"""Leitura da auditoria (só admin). Ninguém grava por aqui: quem grava é o trigger do banco."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select

from app.deps import Sessao, UsuarioAtual, exige
from app.models import Auditoria, Usuario
from app.permissoes import ADMINISTRAR
from app.schemas.auditoria import (Acao, AlteracaoOut, ApagadoOut, EliminacaoOut, EliminarIn, RestauracaoOut,
                                   TabelaAuditada)
from app.servicos import restauracao
from app.servicos.workflow import ErroDeRegra

router = APIRouter(prefix="/auditoria", tags=["Auditoria (admin)"], dependencies=[Depends(exige(ADMINISTRAR))])


@router.get("", response_model=list[AlteracaoOut])
def listar(sessao: Sessao, response: Response, cliente_id: int | None = None, processo_id: int | None = None,
           tabela: TabelaAuditada | None = None, acao: Acao | None = None,
           limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    """Alterações, da mais nova para a mais antiga. Total no cabeçalho X-Total-Count.

    Funciona também para clientes e processos JÁ APAGADOS (é para isso que a auditoria existe): não há 404.
      - `cliente_id`: o cliente e tudo dos processos dele (inclusive pessoas e DS-160);
      - `processo_id`: o processo, seus detalhes, pessoas e DS-160;
      - `tabela` e `acao`: ex.: `tabela=clientes&acao=apagou` lista os clientes removidos."""
    filtros = []
    if processo_id is not None:
        filtros.append(Auditoria.processo_id == processo_id)
    if cliente_id is not None:
        # os processos que um dia foram deste cliente, mesmo os que já não existem
        processos_do_cliente = select(Auditoria.processo_id).where(
            Auditoria.tabela == "processos", Auditoria.cliente_id == cliente_id)
        filtros.append(or_(Auditoria.cliente_id == cliente_id, Auditoria.processo_id.in_(processos_do_cliente)))
    if tabela is not None:
        filtros.append(Auditoria.tabela == tabela)
    if acao is not None:
        filtros.append(Auditoria.acao == acao)
    if tabela is None:
        # o histórico de situações é auditado só para a restauração; já aparece na linha do tempo do processo
        filtros.append(Auditoria.tabela != "eventos")

    response.headers["X-Total-Count"] = str(
        sessao.scalar(select(func.count()).select_from(Auditoria).where(*filtros)))
    consulta = (select(Auditoria, Usuario.nome).outerjoin(Usuario, Usuario.id == Auditoria.usuario_id)
                .where(*filtros).order_by(Auditoria.id.desc()).limit(limit).offset(offset))
    return [AlteracaoOut.model_validate(linha).model_copy(update={"usuario_nome": nome})
            for linha, nome in sessao.execute(consulta)]


# ---------------------------------------------------------------- clientes excluídos

def _traduz(erro: ErroDeRegra) -> HTTPException:
    return HTTPException(status_code=erro.status, detail=erro.mensagem)


@router.get("/apagados", response_model=list[ApagadoOut])
def apagados(sessao: Sessao, response: Response, limit: int = Query(100, ge=1, le=500),
             offset: int = Query(0, ge=0)):
    """Clientes excluídos que ainda dá para restaurar, do mais recente ao mais antigo."""
    itens, total = restauracao.listar_apagados(sessao, limit, offset)
    response.headers["X-Total-Count"] = str(total)
    return itens


@router.post("/apagados/{cliente_id}/restaurar", response_model=RestauracaoOut)
def restaurar(cliente_id: int, sessao: Sessao, admin: UsuarioAtual):
    """Traz de volta o cliente excluído, com processos, pessoas, DS-160 e histórico, com os mesmos números.
    Tudo ou nada: se algum dado único já está em uso de novo (nome, código de DS-160), 409 e nada muda."""
    try:
        resultado = restauracao.restaurar_cliente(sessao, cliente_id, admin)
    except ErroDeRegra as erro:
        raise _traduz(erro)
    sessao.commit()
    return resultado


@router.post("/apagados/{cliente_id}/eliminar", response_model=EliminacaoOut)
def eliminar(cliente_id: int, dados: EliminarIn, sessao: Sessao, admin: UsuarioAtual):
    """ELIMINAÇÃO DEFINITIVA, sem volta: apaga o cliente também da auditoria. Só de quem já foi excluído, só pelo
    admin, repetindo o nome e dando o motivo. Fica uma lápide (número, quem, quando e motivo), sem dado pessoal."""
    try:
        removidas = restauracao.eliminar_definitivamente(sessao, cliente_id, dados.motivo, dados.nome_confirmado,
                                                         admin)
    except ErroDeRegra as erro:
        raise _traduz(erro)
    sessao.commit()
    return {"cliente_id": cliente_id, "linhas_removidas": removidas}
