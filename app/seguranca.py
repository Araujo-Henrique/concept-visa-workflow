"""Senha (hash) e token de acesso (JWT).

Regras que valem aqui:
  - a senha nunca é guardada: só o hash argon2 (lento de propósito e com sal aleatório embutido);
  - o token guarda só o id do usuário e a validade. Perfil e "ativo" NÃO vão no token: a API consulta o
    banco a cada requisição, então mudar o perfil ou desativar alguém vale na hora;
  - o segredo de assinatura vem do ambiente (JWT_SECRET), nunca do código.
"""
import os
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

ALGORITMO = "HS256"
SENHA_MINIMA = 10
SEGREDO_MINIMO = 32

_hasher = PasswordHash.recommended()  # argon2
# hash de uma senha que ninguém usa: serve para gastar o mesmo tempo quando o e-mail não existe
HASH_FALSO = _hasher.hash("senha-que-ninguem-usa-so-para-igualar-o-tempo")


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


def verificar(senha: str, hash_guardado: str) -> bool:
    return _hasher.verify(senha, hash_guardado)


def minutos_de_validade() -> int:
    return int(os.environ.get("JWT_EXPIRA_MINUTOS", "30"))


def _segredo() -> str:
    segredo = os.environ.get("JWT_SECRET", "")
    if len(segredo) < SEGREDO_MINIMO:
        raise RuntimeError(f"Defina JWT_SECRET no .env com pelo menos {SEGREDO_MINIMO} caracteres (veja .env.example)")
    return segredo


def criar_token(usuario_id: int, validade: timedelta | None = None) -> str:
    agora = datetime.now(timezone.utc)
    corpo = {"sub": str(usuario_id), "iat": agora, "exp": agora + (validade or timedelta(minutes=minutos_de_validade()))}
    return jwt.encode(corpo, _segredo(), algorithm=ALGORITMO)


def ler_token(token: str) -> int | None:
    """Devolve o id do usuário se o token for autêntico e estiver na validade; senão None."""
    try:
        # algorithms fixo: impede o ataque de trocar o algoritmo do token (ex.: "none")
        corpo = jwt.decode(token, _segredo(), algorithms=[ALGORITMO], options={"require": ["exp", "sub"]})
        return int(corpo["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
