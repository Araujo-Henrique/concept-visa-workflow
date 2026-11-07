from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app import seguranca
from app.deps import Sessao, UsuarioAtual, _esquema, usuario_atual
from app.schemas.auth import Login, Token, UsuarioOut
from app.schemas.usuario import TrocaDeSenha
from app.servicos.usuarios import trocar_propria_senha
from app.servicos.workflow import ErroDeRegra
from app.servicos.usuarios import achar_por_email

router = APIRouter(prefix="/auth", tags=["Autenticação"])

CREDENCIAIS_INVALIDAS = HTTPException(status_code=401, detail="E-mail ou senha incorretos")


@router.post("/login", response_model=Token)
def login(dados: Login, sessao: Sessao):
    """Troca e-mail e senha por um token de acesso. Todas as falhas dão a mesma resposta (401), para não
    revelar se um e-mail existe."""
    usuario = achar_por_email(sessao, dados.email)
    pode_entrar = usuario is not None and usuario.ativo and usuario.senha_hash is not None
    if not pode_entrar:
        # Usuário inexistente, inativo ou só-Google: a senha digitada nem é conferida com algo real.
        # O hash falso só gasta o mesmo tempo, para ninguém descobrir pela demora quais e-mails existem.
        seguranca.verificar(dados.senha, seguranca.HASH_FALSO)
        raise CREDENCIAIS_INVALIDAS
    if not seguranca.verificar(dados.senha, usuario.senha_hash):
        raise CREDENCIAIS_INVALIDAS
    return Token(access_token=seguranca.criar_token(usuario.id), expira_em_minutos=seguranca.minutos_de_validade())


@router.get("/eu", response_model=UsuarioOut, dependencies=[Depends(usuario_atual)])
def quem_sou_eu(usuario: UsuarioAtual):
    return UsuarioOut.de(usuario)


@router.post("/renovar", response_model=Token)
def renovar(usuario: UsuarioAtual, credenciais: Annotated[HTTPAuthorizationCredentials, Depends(_esquema)]):
    """Sessão deslizante: troca o token atual (ainda válido) por um novo com a validade cheia, enquanto a
    pessoa usa o sistema. Usuário desativado já para no usuario_atual (403). Passado o teto da sessão
    (JWT_SESSAO_MAXIMA_HORAS desde o login), responde 401 e é preciso entrar de novo."""
    renovado = seguranca.renovar_token(credenciais.credentials)
    if renovado is None:
        raise HTTPException(status_code=401, detail="A sessão chegou ao limite. Entre de novo",
                            headers={"WWW-Authenticate": "Bearer"})
    token, minutos = renovado
    return Token(access_token=token, expira_em_minutos=minutos)


@router.post("/senha", status_code=204)
def trocar_senha(dados: TrocaDeSenha, sessao: Sessao, usuario: UsuarioAtual):
    """Qualquer perfil troca a própria senha (precisa da senha atual). Não passa pela regra de método
    porque está fora dos routers protegidos: aqui basta estar logado."""
    try:
        trocar_propria_senha(sessao, usuario, dados.senha_atual, dados.nova_senha)
    except ErroDeRegra as erro:
        raise HTTPException(status_code=erro.status, detail=erro.mensagem)
    sessao.commit()
