"""CRUD dos processos. Os três tipos (OBT, REN, PASS) usam a mesma fábrica de rotas: muda só o modelo
do banco e os schemas. O resto (criar com titular e evento, listar, PATCH validado) é igual."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import Sessao, UsuarioAtual
from app.enums import Consulado, TipoEvento
from app.models import (Cliente, Evento, Processo, ProcessoOBT, ProcessoPASS, ProcessoREN, Solicitante)
from app.routers.comum import aplicar_patch, obter_ou_404
from app.schemas.processo import (OBTBase, OBTCreate, OBTOut, OBTUpdate, PASSBase, PASSCreate, PASSOut,
                                  PASSUpdate, RENBase, RENCreate, RENOut, RENUpdate)

# carrega solicitantes e formulários em consultas à parte, em vez de uma consulta por processo (N+1)
def _carregar(modelo):
    return selectinload(modelo.solicitantes).selectinload(Solicitante.formularios)


def rotas_processo(prefixo: str, modelo: type[Processo], base: type[BaseModel], criar_schema: type[BaseModel],
                   atualizar_schema: type[BaseModel], saida: type[BaseModel], rotulo: str) -> APIRouter:
    router = APIRouter(prefix=prefixo, tags=[rotulo])

    def buscar(sessao, processo_id: int):
        processo = sessao.scalars(
            select(modelo).where(modelo.id == processo_id).options(_carregar(modelo))).one_or_none()
        if processo is None:
            raise HTTPException(status_code=404, detail=f"{rotulo} não encontrado")
        return processo

    @router.post("", response_model=saida, status_code=201)
    def criar(dados: criar_schema, sessao: Sessao, usuario: UsuarioAtual):  # type: ignore[valid-type]
        cliente = sessao.get(Cliente, dados.cliente_id)
        if cliente is None:
            raise HTTPException(status_code=422, detail="Cliente não encontrado")
        if dados.processo_anterior_id is not None:
            anterior = sessao.get(Processo, dados.processo_anterior_id)
            if anterior is None or anterior.cliente_id != cliente.id:
                raise HTTPException(
                    status_code=422, detail="O processo anterior não existe ou é de outro cliente")

        processo = modelo(**dados.model_dump(exclude={"solicitantes_extras"}), criado_por_id=usuario.id)
        # tudo abaixo é gravado numa transação só: ou o processo nasce completo, ou não nasce
        processo.solicitantes.append(Solicitante(nome=cliente.nome, titular=True))
        processo.solicitantes.extend(Solicitante(nome=nome) for nome in dados.solicitantes_extras)
        processo.eventos.append(Evento(tipo=TipoEvento.CRIADO, situacao_nova=dados.situacao, usuario_id=usuario.id))
        sessao.add(processo)
        sessao.commit()
        sessao.refresh(processo)  # traz o que o banco preencheu (id, datas, data_despacho)
        return saida.model_validate(processo)

    @router.get("", response_model=list[saida])
    def listar(sessao: Sessao, cliente_id: int | None = None, situacao: str | None = None,
               consulado: Consulado | None = None,
               limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        consulta = select(modelo).options(_carregar(modelo)).order_by(modelo.id).limit(limit).offset(offset)
        if cliente_id is not None:
            consulta = consulta.where(modelo.cliente_id == cliente_id)
        if situacao:
            consulta = consulta.where(modelo.situacao == situacao)
        if consulado is not None:
            if not hasattr(modelo, "consulado"):
                raise HTTPException(status_code=422, detail="Passaporte não tem consulado")
            consulta = consulta.where(modelo.consulado == consulado)
        return [saida.model_validate(p) for p in sessao.scalars(consulta)]

    @router.get("/{processo_id}", response_model=saida)
    def obter(processo_id: int, sessao: Sessao):
        return saida.model_validate(buscar(sessao, processo_id))

    @router.patch("/{processo_id}", response_model=saida)
    def atualizar(processo_id: int, dados: atualizar_schema, sessao: Sessao):  # type: ignore[valid-type]
        processo = buscar(sessao, processo_id)
        aplicar_patch(base, processo, dados.model_dump(exclude_unset=True))
        sessao.commit()
        sessao.refresh(processo)
        return saida.model_validate(processo)

    @router.delete("/{processo_id}", status_code=204)
    def remover(processo_id: int, sessao: Sessao):
        sessao.delete(buscar(sessao, processo_id))  # solicitantes, formulários e eventos saem junto (cascade)
        sessao.commit()

    return router


router_obt = rotas_processo("/processos-obt", ProcessoOBT, OBTBase, OBTCreate, OBTUpdate, OBTOut,
                            "Processo de obtenção (OBT)")
router_ren = rotas_processo("/processos-ren", ProcessoREN, RENBase, RENCreate, RENUpdate, RENOut,
                            "Processo de renovação (REN)")
router_pass = rotas_processo("/processos-pass", ProcessoPASS, PASSBase, PASSCreate, PASSUpdate, PASSOut,
                             "Processo de passaporte (PASS)")
