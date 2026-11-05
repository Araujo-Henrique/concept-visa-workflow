from typing import Annotated, Iterator

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session as SessaoORM

from app import db, seguranca
from app.models import Usuario


def get_sessao() -> Iterator[SessaoORM]:
    """Uma sessão (transação) por requisição. Se a rota não chamar commit, nada é gravado:
    ao sair, a sessão é fechada e o que estava pendente é desfeito."""
    with db.Session() as sessao:
        yield sessao


Sessao = Annotated[SessaoORM, Depends(get_sessao)]

# HTTPBearer lê o cabeçalho "Authorization: Bearer <token>" e faz o botão "Authorize" aparecer no /docs
_esquema = HTTPBearer(auto_error=False)


def usuario_atual(sessao: Sessao,
                  credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_esquema)]) -> Usuario:
    """Quem está fazendo a requisição. Roda em toda rota protegida.

    O token prova quem é a pessoa; o banco, consultado a cada requisição, diz se ela ainda pode entrar:
    desativar o usuário (ativo = false) corta o acesso na hora, mesmo com um token ainda dentro da validade."""
    nao_autenticado = HTTPException(
        status_code=401, detail="Faça login para acessar", headers={"WWW-Authenticate": "Bearer"})
    if credenciais is None:
        raise nao_autenticado
    usuario_id = seguranca.ler_token(credenciais.credentials)
    if usuario_id is None:
        raise nao_autenticado
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise nao_autenticado
    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Acesso desativado")
    return usuario


UsuarioAtual = Annotated[Usuario, Depends(usuario_atual)]
