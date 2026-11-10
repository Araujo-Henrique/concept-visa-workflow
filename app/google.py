"""Login com o Google (OpenID Connect, fluxo "código de autorização + PKCE").

Quem faz o quê:
  - o front (Next) leva a pessoa ao Google e recebe o `code` de volta;
  - esta API troca o `code` por um `id_token` (aqui fica a chave secreta: só a API a conhece) e o confere;
  - o Google só prova QUEM a pessoa é. Quem pode entrar é decidido pelo cadastro de usuários (rota /auth/google).

O que se confere no id_token, tudo, antes de confiar nele:
  assinatura (chaves públicas do Google), emissor, destinatário (`aud` = o nosso ID de cliente), validade,
  `nonce` (o id_token foi pedido por este login e não é um antigo reaproveitado) e `email_verified`.
"""
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request

import jwt
from jwt import PyJWKClient

URL_TOKEN = "https://oauth2.googleapis.com/token"
URL_CHAVES = "https://www.googleapis.com/oauth2/v3/certs"
EMISSORES = ["https://accounts.google.com", "accounts.google.com"]
TEMPO_LIMITE = 10  # segundos esperando o Google


class ErroGoogle(Exception):
    """O Google recusou ou o id_token não confere. `motivo` vai para o log, nunca para a tela."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


def client_id() -> str:
    return os.environ.get("GOOGLE_CLIENT_ID", "").strip()


def _secret() -> str:
    return os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()


def configurado() -> bool:
    return bool(client_id() and _secret())


def dominio_permitido() -> str:
    return os.environ.get("GOOGLE_ALLOWED_DOMAIN", "").strip().lower().lstrip("@")


def trocar_codigo(codigo: str, verificador: str, redirect_uri: str) -> str:
    """Troca o código (de uso único) pelo id_token. O `verificador` (PKCE) prova que quem troca é quem iniciou."""
    if not configurado():
        raise ErroGoogle("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET não configurados")
    corpo = urllib.parse.urlencode({
        "code": codigo, "client_id": client_id(), "client_secret": _secret(),
        "redirect_uri": redirect_uri, "grant_type": "authorization_code", "code_verifier": verificador,
    }).encode()
    pedido = urllib.request.Request(URL_TOKEN, data=corpo, method="POST",
                                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:
            dados = json.load(resposta)
    except urllib.error.HTTPError as erro:
        # o corpo diz o motivo (ex.: redirect_uri_mismatch, invalid_grant); não tem segredo
        try:
            motivo = json.load(erro).get("error", "")
        except Exception:
            motivo = ""
        raise ErroGoogle(f"o Google recusou o código ({erro.code} {motivo})".strip())
    except (urllib.error.URLError, TimeoutError, ValueError) as erro:
        raise ErroGoogle(f"não consegui falar com o Google ({type(erro).__name__})")
    token = dados.get("id_token")
    if not isinstance(token, str) or not token:
        raise ErroGoogle("a resposta do Google veio sem id_token")
    return token


_chaves: PyJWKClient | None = None


def _cliente_de_chaves() -> PyJWKClient:
    global _chaves
    if _chaves is None:
        _chaves = PyJWKClient(URL_CHAVES, cache_keys=True, lifespan=3600, timeout=TEMPO_LIMITE)
    return _chaves


def validar_id_token(id_token: str, nonce: str) -> dict:
    """Confere o id_token e devolve {"email", "nome"}. Qualquer problema vira ErroGoogle."""
    if not client_id():
        raise ErroGoogle("GOOGLE_CLIENT_ID não configurado")
    try:
        chave = _cliente_de_chaves().get_signing_key_from_jwt(id_token).key
        # algorithms fixo (RS256): impede trocar o algoritmo do token
        corpo = jwt.decode(id_token, chave, algorithms=["RS256"], audience=client_id(), issuer=EMISSORES,
                           leeway=30, options={"require": ["exp", "iat", "aud", "iss", "sub"]})
    except jwt.PyJWTError as erro:
        raise ErroGoogle(f"id_token inválido ({type(erro).__name__})")
    if not nonce or not secrets.compare_digest(str(corpo.get("nonce", "")), nonce):
        raise ErroGoogle("nonce não confere")
    email = str(corpo.get("email", "")).strip()
    if not email or corpo.get("email_verified") is not True:
        raise ErroGoogle("e-mail ausente ou não verificado pelo Google")
    dominio = dominio_permitido()
    if dominio and email.lower().rpartition("@")[2] != dominio:
        raise ErroGoogle(f"e-mail fora do domínio permitido ({dominio})")
    return {"email": email, "nome": str(corpo.get("name", "")).strip()}
