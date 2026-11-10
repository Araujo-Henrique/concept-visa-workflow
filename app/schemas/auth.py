from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import Texto


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Texto
    senha: str = Field(min_length=1, max_length=256)


class LoginGoogle(BaseModel):
    """O que o front recebe do Google na volta e repassa à API (o id_token só a API troca e confere)."""
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=2048)
    code_verifier: str = Field(min_length=43, max_length=128)  # PKCE (RFC 7636)
    nonce: str = Field(min_length=16, max_length=256)
    redirect_uri: str = Field(min_length=1, max_length=512)


class ConfigGoogle(BaseModel):
    client_id: str  # público por natureza (aparece na URL do Google); a chave secreta nunca sai da API


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
