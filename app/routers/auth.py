from fastapi import APIRouter, Depends, HTTPException

from app import seguranca
from app.deps import Sessao, UsuarioAtual, usuario_atual
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


@router.post("/senha", status_code=204)
def trocar_senha(dados: TrocaDeSenha, sessao: Sessao, usuario: UsuarioAtual):
    """Qualquer perfil troca a própria senha (precisa da senha atual). Não passa pela regra de método
    porque está fora dos routers protegidos: aqui basta estar logado."""
    try:
        trocar_propria_senha(sessao, usuario, dados.senha_atual, dados.nova_senha)
    except ErroDeRegra as erro:
        raise HTTPException(status_code=erro.status, detail=erro.mensagem)
    sessao.commit()
