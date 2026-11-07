import re

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, or_, select, update

from app.deps import Sessao
from app.models import Cliente, Processo
from app.routers.comum import aplicar_patch, obter_ou_404
from app.schemas.cliente import ClienteBase, ClienteLista, ClienteOut, ClienteUpdate

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.post("", response_model=ClienteOut, status_code=201)
def criar(dados: ClienteBase, sessao: Sessao):
    cliente = Cliente(**dados.model_dump())
    sessao.add(cliente)
    sessao.commit()  # nome repetido: o índice único do banco recusa e o handler devolve 409
    return ClienteOut.model_validate(cliente)


@router.get("", response_model=list[ClienteLista])
def listar(sessao: Sessao, response: Response, busca: str | None = None, nome: str | None = None,
           grupo: str | None = None, telefone: str | None = None,
           limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    """Clientes em ordem alfabética, com quantos processos cada um tem. `busca` procura no nome, no e-mail e
    nos dígitos do telefone de uma vez (é o campo de busca da tela). Total no cabeçalho X-Total-Count."""
    filtros = []
    if busca and busca.strip():
        termo = busca.strip().lower()
        # strpos() em vez de ILIKE: o trecho pode ter % ou _ sem virar curinga
        opcoes = [func.strpos(func.lower(Cliente.nome), termo) > 0,
                  func.strpos(func.lower(func.coalesce(Cliente.email, "")), termo) > 0]
        digitos = re.sub(r"\D", "", termo)
        if digitos:
            opcoes.append(func.strpos(func.coalesce(Cliente.telefone, ""), digitos) > 0)
        filtros.append(or_(*opcoes))
    if nome:
        filtros.append(func.strpos(func.lower(Cliente.nome), nome.lower()) > 0)
    if grupo:
        filtros.append(Cliente.grupo == grupo)
    if telefone:
        filtros.append(Cliente.telefone == telefone)

    response.headers["X-Total-Count"] = str(sessao.scalar(select(func.count()).select_from(Cliente).where(*filtros)))
    n_processos = (select(func.count()).where(Processo.cliente_id == Cliente.id)
                   .correlate(Cliente).scalar_subquery())
    consulta = (select(Cliente, n_processos).where(*filtros)
                .order_by(func.lower(Cliente.nome), Cliente.id).limit(limit).offset(offset))
    return [ClienteLista.model_validate(c).model_copy(update={"n_processos": n})
            for c, n in sessao.execute(consulta)]


@router.get("/{cliente_id}", response_model=ClienteOut)
def obter(cliente_id: int, sessao: Sessao):
    return ClienteOut.model_validate(obter_ou_404(sessao, Cliente, cliente_id, "Cliente"))


@router.patch("/{cliente_id}", response_model=ClienteOut)
def atualizar(cliente_id: int, dados: ClienteUpdate, sessao: Sessao):
    cliente = obter_ou_404(sessao, Cliente, cliente_id, "Cliente")
    aplicar_patch(ClienteBase, cliente, dados.model_dump(exclude_unset=True))
    sessao.commit()
    return ClienteOut.model_validate(cliente)


@router.delete("/{cliente_id}", status_code=204)
def remover(cliente_id: int, sessao: Sessao,
            com_processos: bool = Query(False, description="Apaga também os processos do cliente")):
    """Apaga o cliente do banco (ex.: desistiu e pediu para ser retirado). Só admin: DELETE exige a permissão
    `apagar`. Com processos, só apaga se `com_processos=true`: aí saem junto os processos, solicitantes,
    formulários e eventos. Não há lixeira: a remoção é definitiva."""
    cliente = obter_ou_404(sessao, Cliente, cliente_id, "Cliente")
    processos = list(cliente.processos)
    if processos and not com_processos:
        raise HTTPException(status_code=409, detail=(
            f"O cliente tem {len(processos)} processo(s). Para apagar junto, confirme com com_processos=true"))
    ids = [p.id for p in processos]
    if ids:
        # outra tentativa que aponte para um destes processos perde só a referência, não é apagada
        sessao.execute(update(Processo).where(Processo.processo_anterior_id.in_(ids), Processo.id.not_in(ids))
                       .values(processo_anterior_id=None))
        for processo in processos:
            processo.processo_anterior_id = None
        sessao.flush()
        for processo in processos:
            sessao.delete(processo)  # solicitantes, formulários e eventos saem junto (cascade)
        sessao.flush()
    sessao.delete(cliente)
    sessao.commit()
