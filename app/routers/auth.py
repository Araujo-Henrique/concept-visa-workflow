import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from app import google, limites, seguranca
from app.deps import Sessao, UsuarioAtual, _esquema, usuario_atual
from app.schemas.auth import ConfigGoogle, Login, LoginGoogle, Token, UsuarioOut
from app.schemas.usuario import TrocaDeSenha
from app.servicos.usuarios import trocar_propria_senha
from app.servicos.workflow import ErroDeRegra
from app.servicos.usuarios import achar_por_email

router = APIRouter(prefix="/auth", tags=["Autenticação"])

CREDENCIAIS_INVALIDAS = HTTPException(status_code=401, detail="E-mail ou senha incorretos")

registro = logging.getLogger("concept.acesso")


def _muitas_tentativas(segundos: int) -> HTTPException:
    return HTTPException(status_code=429, detail=limites.mensagem_de_espera(segundos),
                         headers={"Retry-After": str(segundos)})


def _mascarar(email: str) -> str:
    """Para o log: dá para reconhecer a conta sem gravar o e-mail inteiro (a.***@dominio.com)."""
    nome, _, dominio = email.partition("@")
    return f"{nome[:1]}***@{dominio}"


@router.post("/login", response_model=Token)
def login(dados: Login, sessao: Sessao, request: Request):
    """Troca e-mail e senha por um token de acesso. SÓ ADMINISTRADORES entram com senha; os demais usam o
    Google (POST /auth/google). Todas as falhas dão a mesma resposta (401), para não revelar se um e-mail
    existe, se a senha está certa ou qual é o perfil.

    Contra quem tenta adivinhar senhas: cada IP tem poucas tentativas por minuto e cada conta, poucas senhas
    erradas em 15 minutos. Passou disso, 429 com o tempo de espera, inclusive com a senha certa (senão o robô
    saberia quando acertou). A trava vale para qualquer e-mail digitado, exista ou não, pelo mesmo motivo."""
    ip = limites.ip_do_cliente(request)
    if espera := limites.login_por_ip.registrar(ip):
        registro.warning("login bloqueado por excesso de tentativas do IP %s", ip)
        raise _muitas_tentativas(espera)
    conta = dados.email.strip().lower()
    if espera := limites.falhas_por_conta.espera(conta):
        registro.warning("login bloqueado: conta %s travada (IP %s)", _mascarar(conta), ip)
        raise _muitas_tentativas(espera)

    usuario = achar_por_email(sessao, dados.email)
    pode_entrar = (usuario is not None and usuario.ativo and usuario.senha_hash is not None
                   and usuario.perfil.nome == "admin")
    if not pode_entrar:
        # Usuário inexistente, inativo, sem senha ou que não é admin: a senha digitada nem é conferida com algo real.
        # O hash falso só gasta o mesmo tempo, para ninguém descobrir pela demora quais e-mails existem.
        seguranca.verificar(dados.senha, seguranca.HASH_FALSO)
    if not pode_entrar or not seguranca.verificar(dados.senha, usuario.senha_hash):
        limites.falhas_por_conta.registrar(conta)
        registro.warning("login falhou para %s (IP %s)", _mascarar(conta), ip)
        raise CREDENCIAIS_INVALIDAS
    limites.falhas_por_conta.esquecer(conta)
    return Token(access_token=seguranca.criar_token(usuario.id, versao=usuario.token_version), expira_em_minutos=seguranca.minutos_de_validade())


@router.get("/google/config", response_model=ConfigGoogle)
def config_google():
    """O front precisa do ID de cliente para montar o endereço de login do Google (não é segredo)."""
    if not google.configurado():
        raise HTTPException(status_code=503, detail="Login com o Google não está configurado")
    return ConfigGoogle(client_id=google.client_id())


@router.post("/google", response_model=Token)
def login_google(dados: LoginGoogle, sessao: Sessao, request: Request):
    """Login com o Google. O Google prova quem é a pessoa; a decisão é nossa: só entra quem tem o e-mail
    cadastrado em Usuários e ativo (senão 403, sem criar nada). O perfil vem do cadastro, nunca do Google."""
    ip = limites.ip_do_cliente(request)
    if espera := limites.login_por_ip.registrar(ip):
        registro.warning("login Google bloqueado por excesso de tentativas do IP %s", ip)
        raise _muitas_tentativas(espera)
    try:
        identidade = google.validar_id_token(
            google.trocar_codigo(dados.code, dados.code_verifier, dados.redirect_uri), dados.nonce)
    except google.ErroGoogle as erro:
        registro.warning("login Google recusado (IP %s): %s", ip, erro.motivo)
        raise HTTPException(status_code=401, detail="Não foi possível confirmar o login com o Google")
    usuario = achar_por_email(sessao, identidade["email"])
    if usuario is None or not usuario.ativo:
        registro.warning("login Google sem acesso: %s %s (IP %s)", _mascarar(identidade["email"].lower()),
                         "desativado" if usuario else "não cadastrado", ip)
        raise HTTPException(status_code=403, detail="Este e-mail não tem acesso ao sistema")
    registro.info("login Google: %s (IP %s)", _mascarar(usuario.email.lower()), ip)
    return Token(access_token=seguranca.criar_token(usuario.id, versao=usuario.token_version), expira_em_minutos=seguranca.minutos_de_validade())


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


@router.post("/senha", response_model=Token)
def trocar_senha(dados: TrocaDeSenha, sessao: Sessao, usuario: UsuarioAtual):
    """Qualquer perfil troca a própria senha (precisa da senha atual). Não passa pela regra de método
    porque está fora dos routers protegidos: aqui basta estar logado. Errar a senha atual conta como no
    login (quem pegou um computador logado não fica testando senhas)."""
    if usuario.perfil.nome != "admin":
        raise HTTPException(status_code=403, detail="Só administradores usam senha; você entra com o Google")
    chave = f"troca-de-senha:{usuario.id}"
    if espera := limites.falhas_por_conta.espera(chave):
        raise _muitas_tentativas(espera)
    try:
        trocar_propria_senha(sessao, usuario, dados.senha_atual, dados.nova_senha)
    except ErroDeRegra as erro:
        if erro.mensagem == "Senha atual incorreta":
            limites.falhas_por_conta.registrar(chave)
        raise HTTPException(status_code=erro.status, detail=erro.mensagem)
    limites.falhas_por_conta.esquecer(chave)
    sessao.commit()
    # as outras sessões caíram (token_version subiu); esta continua com um token da versão nova
    return Token(access_token=seguranca.criar_token(usuario.id, versao=usuario.token_version),
                 expira_em_minutos=seguranca.minutos_de_validade())
