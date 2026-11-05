from pydantic import BaseModel, ConfigDict

from app.schemas.comum import Texto


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Texto
    senha: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_em_minutos: int


class UsuarioOut(BaseModel):
    """O que a API mostra de um usuário. O senha_hash nunca sai: este schema não o declara."""
    id: int
    nome: str
    email: str
    ativo: bool
    perfil: str

    @classmethod
    def de(cls, usuario) -> "UsuarioOut":
        return cls(id=usuario.id, nome=usuario.nome, email=usuario.email, ativo=usuario.ativo,
                   perfil=usuario.perfil.nome)
