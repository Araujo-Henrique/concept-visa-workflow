from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class PainelBase(BaseModel):
    """Campos comuns a todo processo: quem é, quantos são e como está."""
    processo_id: int
    situacao: str
    cliente_id: int
    cliente: str
    telefone: str | None
    grupo: str | None
    titular: str | None
    n_solicitantes: int
    solicitantes: str  # nomes separados por vírgula, titular primeiro
    resultado_geral: str  # Processando, Aprovado, Negado ou Parcial (resultados diferentes)
    n_formularios: int
    atualizado_em: datetime


# Cada tipo mostra só os campos que fazem sentido para ele (um OBT não tem data de PF, um passaporte
# não tem consulado). A view do banco devolve todas as colunas; o schema escolhe quais seguem para a API.

class PainelOBT(PainelBase):
    tipo: Literal["OBT"]
    consulado: str | None  # vazio no histórico com consulado N/D
    data_casv: date | None
    data_entrevista: date | None
    codigo_rastreio: str | None
    orientacao: str | None  # Opt A, Fornecidas, Agendada ou Pendente
    orientacao_data: date | None
    orientacao_por: str | None  # vazio quando ninguém foi indicado (comum no histórico antigo)


class PainelREN(PainelBase):
    tipo: Literal["REN"]
    consulado: str | None
    data_casv: date | None
    data_despacho: date | None
    codigo_rastreio: str | None


class PainelPASS(PainelBase):
    tipo: Literal["PASS"]
    data_pf: date | None
    prazo_pf: date | None


PainelOut = Annotated[PainelOBT | PainelREN | PainelPASS, Field(discriminator="tipo")]
painel_adapter = TypeAdapter(PainelOut)


class ResumoTipo(BaseModel):
    total: int
    por_situacao: dict[str, int]
    por_resultado: dict[str, int]  # resultado_geral: Processando, Aprovado, Negado ou Parcial


class AgendaItem(BaseModel):
    data: date
    evento: Literal["orientacao", "casv", "entrevista", "despacho", "pf", "prazo_pf"]
    processo_id: int
    tipo: Literal["OBT", "REN", "PASS"]
    cliente: str
    situacao: str
    consulado: str | None
