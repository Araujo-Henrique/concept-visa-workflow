"""Solicitantes de um processo e os formulários DS-160 de cada um."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.deps import Sessao
from app.models import FormularioDS160, Processo, Solicitante
from app.routers.comum import obter_ou_404
from app.schemas.solicitante import (FormularioNovo, FormularioOut, FormularioUpdate, SolicitanteNovo,
                                     SolicitanteOut, SolicitanteUpdate)

router = APIRouter(tags=["Solicitantes e DS-160"])


@router.get("/processos/{processo_id}/solicitantes", response_model=list[SolicitanteOut])
def listar(processo_id: int, sessao: Sessao):
    processo = obter_ou_404(sessao, Processo, processo_id, "Processo")
    return [SolicitanteOut.model_validate(s) for s in processo.solicitantes]


@router.post("/processos/{processo_id}/solicitantes", response_model=SolicitanteOut, status_code=201)
def adicionar(processo_id: int, dados: SolicitanteNovo, sessao: Sessao):
    processo = obter_ou_404(sessao, Processo, processo_id, "Processo")
    solicitante = Solicitante(processo_id=processo.id, nome=dados.nome)  # nunca titular: o titular já existe
    sessao.add(solicitante)
    sessao.commit()
    return SolicitanteOut.model_validate(solicitante)


@router.patch("/solicitantes/{solicitante_id}", response_model=SolicitanteOut)
def atualizar(solicitante_id: int, dados: SolicitanteUpdate, sessao: Sessao):
    solicitante = obter_ou_404(sessao, Solicitante, solicitante_id, "Solicitante")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if valor is None:
            raise HTTPException(status_code=422, detail=f"'{campo}' não pode ser vazio")
        setattr(solicitante, campo, valor)
    sessao.commit()
    return SolicitanteOut.model_validate(solicitante)


@router.post("/solicitantes/{solicitante_id}/titular", response_model=SolicitanteOut)
def tornar_titular(solicitante_id: int, sessao: Sessao):
    """Troca o titular do processo. O índice único do banco permite um titular só, então a ordem importa:
    primeiro tira de quem era, grava (flush), e só depois promove o novo."""
    novo = obter_ou_404(sessao, Solicitante, solicitante_id, "Solicitante")
    for outro in novo.processo.solicitantes:
        if outro.titular and outro.id != novo.id:
            outro.titular = False
    sessao.flush()
    novo.titular = True
    sessao.commit()
    return SolicitanteOut.model_validate(novo)


@router.delete("/solicitantes/{solicitante_id}", status_code=204)
def remover(solicitante_id: int, sessao: Sessao):
    solicitante = obter_ou_404(sessao, Solicitante, solicitante_id, "Solicitante")
    if solicitante.titular:
        raise HTTPException(
            status_code=409, detail="O titular não pode ser removido; torne outro solicitante titular antes")
    sessao.delete(solicitante)
    sessao.commit()


# ---------------------------------------------------------------- DS-160

@router.post("/solicitantes/{solicitante_id}/formularios-ds160", response_model=FormularioOut, status_code=201)
def adicionar_formulario(solicitante_id: int, dados: FormularioNovo, sessao: Sessao):
    solicitante = obter_ou_404(sessao, Solicitante, solicitante_id, "Solicitante")
    if sessao.scalars(select(FormularioDS160).where(FormularioDS160.codigo == dados.codigo)).first():
        raise HTTPException(status_code=409, detail="Esse código de DS-160 já está cadastrado")
    formulario = FormularioDS160(solicitante_id=solicitante.id, **dados.model_dump())
    sessao.add(formulario)
    sessao.commit()
    return FormularioOut.model_validate(formulario)


@router.patch("/formularios-ds160/{formulario_id}", response_model=FormularioOut)
def atualizar_formulario(formulario_id: int, dados: FormularioUpdate, sessao: Sessao):
    formulario = obter_ou_404(sessao, FormularioDS160, formulario_id, "Formulário")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if campo == "status" and valor is None:
            raise HTTPException(status_code=422, detail="'status' não pode ser vazio")
        setattr(formulario, campo, valor)
    sessao.commit()
    return FormularioOut.model_validate(formulario)


@router.delete("/formularios-ds160/{formulario_id}", status_code=204)
def remover_formulario(formulario_id: int, sessao: Sessao):
    sessao.delete(obter_ou_404(sessao, FormularioDS160, formulario_id, "Formulário"))
    sessao.commit()
