import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import Resultado, StatusDS
from app.schemas.comum import Texto, TextoLivre

PADRAO_CODIGO = re.compile(r"^AA00[A-Z0-9]{6}$")


class FormularioNovo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str = Field(max_length=20)
    status: StatusDS = StatusDS.PENDENTE
    observacao: TextoLivre | None = None

    @field_validator("codigo")
    @classmethod
    def codigo_no_padrao(cls, valor):
        valor = valor.strip().upper()
        if not PADRAO_CODIGO.match(valor):
            raise ValueError("O código do DS-160 tem 10 caracteres: AA00 seguido de 6 letras ou números")
        return valor


class FormularioUpdate(BaseModel):
    """O código não muda depois de criado: se está errado, remova e cadastre de novo."""
    model_config = ConfigDict(extra="forbid")

    status: StatusDS | None = None
    observacao: TextoLivre | None = None


class FormularioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    solicitante_id: int
    codigo: str
    status: StatusDS
    observacao: str | None


class SolicitanteNovo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: Texto


class SolicitanteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: Texto | None = None
    resultado: Resultado | None = None


class SolicitanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    processo_id: int
    nome: str
    titular: bool
    resultado: Resultado
    formularios: list[FormularioOut] = []
