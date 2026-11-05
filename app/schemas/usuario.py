from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.comum import Texto


class UsuarioNovo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: Texto
    email: Texto
    perfil: str
    senha: str | None = None  # sem senha: o usuário só poderá entrar com o Google (etapa futura)


class UsuarioUpdate(BaseModel):
    """O e-mail não muda: ele é a identidade do usuário (login e, no futuro, Google)."""
    model_config = ConfigDict(extra="forbid")

    nome: Texto | None = None
    perfil: str | None = None
    ativo: bool | None = None


class NovaSenha(BaseModel):
    model_config = ConfigDict(extra="forbid")

    senha: str


class TrocaDeSenha(BaseModel):
    model_config = ConfigDict(extra="forbid")

    senha_atual: str
    nova_senha: str


class AuditoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    feito_por_id: int | None
    campo: str
    valor_anterior: str | None
    valor_novo: str | None
    criado_em: datetime
