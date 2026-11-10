from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import Texto, texto


class UsuarioNovo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: texto(120)
    email: Texto
    perfil: str = Field(max_length=30)
    senha: str | None = Field(default=None, max_length=256)  # só para admin; os demais perfis entram com o Google (sem senha)


class UsuarioUpdate(BaseModel):
    """O e-mail não muda: ele é a identidade do usuário (é com ele que o Google identifica a pessoa)."""
    model_config = ConfigDict(extra="forbid")

    nome: texto(120) | None = None
    perfil: str | None = Field(default=None, max_length=30)
    ativo: bool | None = None


class NovaSenha(BaseModel):
    model_config = ConfigDict(extra="forbid")

    senha: str = Field(max_length=256)


class TrocaDeSenha(BaseModel):
    model_config = ConfigDict(extra="forbid")

    senha_atual: str = Field(max_length=256)
    nova_senha: str = Field(max_length=256)


class AuditoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    feito_por_id: int | None
    campo: str
    valor_anterior: str | None
    valor_novo: str | None
    criado_em: datetime
