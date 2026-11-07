"""Senha (hash) e token de acesso (JWT).

Regras que valem aqui:
  - a senha nunca é guardada: só o hash argon2 (lento de propósito e com sal aleatório embutido);
  - o token guarda só o id do usuário e a validade. Perfil e "ativo" NÃO vão no token: a API consulta o
    banco a cada requisição, então mudar o perfil ou desativar alguém vale na hora;
  - o segredo de assinatura vem do ambiente (JWT_SECRET), nunca do código;
  - sessão deslizante: enquanto a pessoa usa o sistema, o front troca o token por um novo (POST /auth/renovar).
    O token guarda quando foi o login ("ini") e a renovação nunca passa de JWT_SESSAO_MAXIMA_HORAS depois dele:
    quem fica o dia inteiro logado entra de novo no dia seguinte.
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


def horas_maximas_da_sessao() -> float:
    return float(os.environ.get("JWT_SESSAO_MAXIMA_HORAS", "10"))


def _segredo() -> str:
    segredo = os.environ.get("JWT_SECRET", "")
    if len(segredo) < SEGREDO_MINIMO:
        raise RuntimeError(f"Defina JWT_SECRET no .env com pelo menos {SEGREDO_MINIMO} caracteres (veja .env.example)")
    return segredo


def criar_token(usuario_id: int, validade: timedelta | None = None, inicio: datetime | None = None) -> str:
    """Token novo. `inicio` é a hora do login (numa renovação, a do login original): a validade nunca passa
    do teto da sessão contado a partir dele."""
    agora = datetime.now(timezone.utc)
    inicio = inicio or agora
    expira = min(agora + (validade or timedelta(minutes=minutos_de_validade())),
                 inicio + timedelta(hours=horas_maximas_da_sessao()))
    corpo = {"sub": str(usuario_id), "iat": agora, "ini": int(inicio.timestamp()), "exp": expira}
    return jwt.encode(corpo, _segredo(), algorithm=ALGORITMO)


def _ler(token: str) -> dict | None:
    try:
        # algorithms fixo: impede o ataque de trocar o algoritmo do token (ex.: "none")
        corpo = jwt.decode(token, _segredo(), algorithms=[ALGORITMO], options={"require": ["exp", "sub"]})
        int(corpo["sub"])
        return corpo
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        return None


def ler_token(token: str) -> int | None:
    """Devolve o id do usuário se o token for autêntico e estiver na validade; senão None."""
    corpo = _ler(token)
    return None if corpo is None else int(corpo["sub"])


def renovar_token(token: str) -> tuple[str, int] | None:
    """Troca um token válido por um novo, mantendo a hora do login. Devolve (token, minutos que ele vale) ou
    None quando o teto da sessão já chegou (falta menos de 1 minuto): aí só entrando de novo."""
    corpo = _ler(token)
    if corpo is None:
        return None
    inicio = datetime.fromtimestamp(corpo.get("ini") or corpo.get("iat") or 0, timezone.utc)
    agora = datetime.now(timezone.utc)
    teto = inicio + timedelta(hours=horas_maximas_da_sessao())
    minutos = int(min(timedelta(minutes=minutos_de_validade()), teto - agora).total_seconds() // 60)
    if minutos < 1:
        return None
    return criar_token(int(corpo["sub"]), validade=timedelta(minutes=minutos), inicio=inicio), minutos
