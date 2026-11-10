from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TabelaAuditada = Literal["clientes", "processos", "processo_obt", "processo_ren", "processo_pass", "solicitantes",
                         "formularios_ds160", "eventos"]
Acao = Literal["criou", "editou", "apagou", "eliminou"]


class AlteracaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tabela: str
    registro_id: int
    processo_id: int | None
    cliente_id: int | None
    acao: str
    antes: dict | None
    depois: dict | None
    usuario_id: int | None
    usuario_nome: str | None = None
    requisicao: str | None
    origem: str
    transacao: int
    criado_em: datetime


class ApagadoOut(BaseModel):
    """Um cliente excluído que ainda tem cópia na auditoria (dá para restaurar ou eliminar de vez)."""
    cliente_id: int
    nome: str
    telefone: str | None
    email: str | None
    apagado_em: datetime
    usuario_id: int | None
    apagado_por: str | None
    origem: str
    n_processos: int


class RestauracaoOut(BaseModel):
    cliente_id: int
    nome: str
    processos: int
    pessoas: int
    formularios: int
    eventos: int
    vinculos: int


class EliminarIn(BaseModel):
    """O pedido de eliminação definitiva. O nome repete a confirmação da tela (a API também confere)."""
    model_config = ConfigDict(extra="forbid")

    nome_confirmado: str
    motivo: str = Field(min_length=5, max_length=300, description="Por que (não escreva dados pessoais aqui)")


class EliminacaoOut(BaseModel):
    cliente_id: int
    linhas_removidas: int
