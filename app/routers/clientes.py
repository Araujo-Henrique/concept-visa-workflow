from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.deps import Sessao
from app.models import Cliente
from app.routers.comum import aplicar_patch, obter_ou_404
from app.schemas.cliente import ClienteBase, ClienteOut, ClienteUpdate

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.post("", response_model=ClienteOut, status_code=201)
def criar(dados: ClienteBase, sessao: Sessao):
    cliente = Cliente(**dados.model_dump())
    sessao.add(cliente)
    sessao.commit()  # nome repetido: o índice único do banco recusa e o handler devolve 409
    return ClienteOut.model_validate(cliente)


@router.get("", response_model=list[ClienteOut])
def listar(sessao: Sessao, nome: str | None = None, grupo: str | None = None, telefone: str | None = None,
           limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    consulta = select(Cliente).order_by(Cliente.id).limit(limit).offset(offset)
    if nome:
        # strpos() em vez de ILIKE: o trecho pode ter % ou _ sem virar curinga
        consulta = consulta.where(func.strpos(func.lower(Cliente.nome), nome.lower()) > 0)
    if grupo:
        consulta = consulta.where(Cliente.grupo == grupo)
    if telefone:
        consulta = consulta.where(Cliente.telefone == telefone)
    return [ClienteOut.model_validate(c) for c in sessao.scalars(consulta)]


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
def remover(cliente_id: int, sessao: Sessao):
    cliente = obter_ou_404(sessao, Cliente, cliente_id, "Cliente")
    if cliente.processos:
        raise HTTPException(status_code=409, detail="O cliente tem processos vinculados e não pode ser apagado")
    sessao.delete(cliente)
    sessao.commit()
