"""Schemas dos três tipos de processo.

Para cada tipo há:
  *Base    campos do tipo + regras entre campos (a "verdade" do que é um processo válido)
  *Create  Base + o que só existe na criação (cliente, situação inicial, solicitantes extras)
  *Update  Base com tudo opcional (PATCH)
  *Out     o que a API devolve
"""
from datetime import date, datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from app.enums import (SITUACOES, Consulado, DocsREN, Monitoramento, Orientacao, Rascunho, TipoProcesso)
from app.schemas.comum import MAX_PESSOAS_POR_PROCESSO, Texto, TextoLivre, atualizacao, texto
from app.schemas.solicitante import SolicitanteOut


def mexeu(info: ValidationInfo, *campos: str) -> bool:
    """A validação veio de um PATCH que alterou algum destes campos? Sem contexto (criação), vale sempre."""
    alterados = (info.context or {}).get("alterados")
    return alterados is None or bool(alterados & set(campos))


class NovoProcesso(BaseModel):
    """Campos que só existem ao criar. A situação de um processo existente muda por rota própria."""
    TIPO: ClassVar[TipoProcesso]

    cliente_id: int
    situacao: str
    # além do titular, que é criado com o nome do cliente
    solicitantes_extras: list[Texto] = Field(default=[], max_length=MAX_PESSOAS_POR_PROCESSO - 1)
    processo_anterior_id: int | None = None  # nova tentativa de um processo anterior

    @model_validator(mode="after")
    def _situacao_do_tipo(self):
        if self.situacao not in SITUACOES[self.TIPO]:
            raise ValueError(f"Situação inválida para {self.TIPO.value}: use uma de {SITUACOES[self.TIPO]}")
        return self


class ProcessoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    cliente_id: int
    situacao: str
    processo_anterior_id: int | None
    criado_em: datetime
    atualizado_em: datetime
    solicitantes: list[SolicitanteOut]


# ---------------------------------------------------------------- OBT

class OBTBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consulado: Consulado | None = None  # pode ficar vazio até haver data marcada
    monitoramento: Monitoramento = Monitoramento.ATIVO
    data_casv: date | None = None
    data_entrevista: date | None = None
    data_vencimento_taxa: date | None = None
    status_rascunho: Rascunho = Rascunho.PENDENTE
    orientacao: Orientacao = Orientacao.PENDENTE
    orientacao_data: date | None = None
    orientacao_por_id: int | None = None  # id de um usuário
    codigo_rastreio: texto(60) | None = None
    observacao: TextoLivre | None = None

    @model_validator(mode="after")
    def _regras(self, info: ValidationInfo):
        if self.orientacao == Orientacao.AGENDADA and self.orientacao_data is None:
            raise ValueError("Orientação 'Agendada' exige a data da orientação")
        # No PATCH, a regra do consulado só é cobrada se a edição mexe nos campos dela: o histórico importado
        # tem processos com data e consulado vazio (era "N/D") que precisam poder ser editados no resto.
        if (self.data_casv or self.data_entrevista) and self.consulado is None and                 mexeu(info, "consulado", "data_casv", "data_entrevista"):
            raise ValueError("Com data de CASV ou entrevista, informe o consulado")
        return self


class OBTCreate(NovoProcesso, OBTBase):
    TIPO = TipoProcesso.OBT


OBTUpdate = atualizacao(OBTBase, "OBTUpdate")


class OBTOut(ProcessoOut, OBTBase):
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _regras(self):
        # Saída mostra o que está gravado. As regras entre campos valem ao criar e editar; o histórico
        # importado tem processos com data e consulado vazio (era "N/D"), que precisam continuar legíveis.
        return self


# ---------------------------------------------------------------- REN

class RENBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consulado: Consulado | None = None
    data_casv: date | None = None
    docs: DocsREN = DocsREN.PENDENTE
    status_rascunho: Rascunho = Rascunho.PENDENTE
    endereco: TextoLivre | None = None
    codigo_rastreio: texto(60) | None = None
    despachado_em: date | None = None  # vazio = ainda falta despachar
    observacao: TextoLivre | None = None

    @model_validator(mode="after")
    def _regras(self, info: ValidationInfo):
        if self.data_casv and self.consulado is None:
            raise ValueError("Com data de CASV, informe o consulado")
        if self.despachado_em and self.despachado_em > date.today() and mexeu(info, "despachado_em"):
            raise ValueError("A data do despacho não pode ser no futuro")
        return self


class RENCreate(NovoProcesso, RENBase):
    TIPO = TipoProcesso.REN


RENUpdate = atualizacao(RENBase, "RENUpdate")


class RENOut(ProcessoOut, RENBase):
    model_config = ConfigDict(from_attributes=True)

    data_despacho: date | None  # calculada pelo banco: CASV - 7 dias

    @model_validator(mode="after")
    def _regras(self):
        return self  # mesma razão do OBTOut: a saída nunca recusa o que já está gravado


# ---------------------------------------------------------------- PASS

class PASSBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_pf: date | None = None
    prazo_pf: date | None = None
    observacao: TextoLivre | None = None


class PASSCreate(NovoProcesso, PASSBase):
    TIPO = TipoProcesso.PASS


PASSUpdate = atualizacao(PASSBase, "PASSUpdate")


class PASSOut(ProcessoOut, PASSBase):
    model_config = ConfigDict(from_attributes=True)
