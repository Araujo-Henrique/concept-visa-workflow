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
    orientacao: str | None  # um dos valores de app.enums.Orientacao
    orientacao_data: date | None
    orientacao_por: str | None  # vazio quando ninguém foi indicado (comum no histórico antigo)
    previsao_orientacao: date | None  # CASV - 14 dias; só previsão, não muda o status da orientação
    ds160_status: str | None  # o status MENOS avançado entre os DS-160 do processo; nulo se não há nenhum
    ds160_fechados: int  # quantos DS-160 já estão Fechado (com n_formularios: "2 de 3")


class PainelREN(PainelBase):
    tipo: Literal["REN"]
    consulado: str | None
    data_casv: date | None
    data_despacho: date | None  # prazo (CASV - 7)
    despachado_em: date | None  # quando foi despachado; vazio = falta despachar
    codigo_rastreio: str | None
    ds160_status: str | None  # o status MENOS avançado entre os DS-160 do processo; nulo se não há nenhum
    ds160_fechados: int


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
    despachado_em: date | None = None  # só no evento "despacho": quando foi feito
