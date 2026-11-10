from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.comum import Texto, atualizacao, texto


class ClienteBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: Texto
    email: Texto | None = None
    telefone: str | None = Field(default=None, max_length=40)  # como digitado; depois fica só com dígitos (até 20)
    grupo: texto(100) | None = None

    @field_validator("telefone")
    @classmethod
    def telefone_so_digitos(cls, valor):
        # guardado só com dígitos e sem o 55 do Brasil (mesma regra do Projeto 1)
        if valor is None:
            return None
        digitos = "".join(c for c in valor if c.isdigit())
        if len(digitos) > 11 and digitos.startswith("55"):
            digitos = digitos[2:]
        if len(digitos) > 20:
            raise ValueError("O telefone tem dígitos demais (no máximo 20)")
        return digitos or None


ClienteUpdate = atualizacao(ClienteBase, "ClienteUpdate")


class ClienteOut(ClienteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ClienteLista(ClienteOut):
    n_processos: int = 0  # quantos processos o cliente tem (lista da tela de clientes)
