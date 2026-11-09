"""Logs da API: um registro por requisição e um código (id) que liga tudo o que aconteceu nela.

Por que um id: quando alguém avisa "deu erro às 14h", o código que a tela mostra leva direto às linhas do
log daquela requisição (a requisição em si, o login bloqueado, a exceção com o traceback...).

O que NUNCA entra no log: senha, token, corpo da requisição e parâmetros da URL (a busca pode ter nome ou
telefone de cliente). Só método, caminho, status, duração, usuário (id) e IP.

Configuração por ambiente:
  - LOG_NIVEL: DEBUG, INFO (padrão), WARNING ou ERROR;
  - LOG_FORMATO: `texto` (padrão, para ler no terminal) ou `json` (uma linha por registro, para ferramentas);
  - LOG_ARQUIVO: caminho de um arquivo (ex.: logs/api.log). Vazio = só terminal. Com rotação: ao chegar em
    LOG_ARQUIVO_MB (padrão 5), o arquivo vira .1, o .1 vira .2... e só ficam LOG_ARQUIVO_COPIAS (padrão 5)
    cópias; a mais antiga é apagada. O espaço em disco nunca passa de (copias + 1) x tamanho.
"""
import contextvars
import json
import logging
import os
import re
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone

# Vale para a requisição em andamento (cada requisição enxerga o seu). "-" fora de uma requisição.
id_da_requisicao: contextvars.ContextVar[str] = contextvars.ContextVar("id_da_requisicao", default="-")

# Um id vindo de fora (ex.: do Next) só é aceito se for curto e sem símbolos: ninguém injeta linhas falsas no log.
_ID_VALIDO = re.compile(r"[A-Za-z0-9._-]{1,64}")

NOME_DO_LOGGER = "concept"


def novo_id(recebido: str | None = None) -> str:
    if recebido and _ID_VALIDO.fullmatch(recebido):
        return recebido
    return uuid.uuid4().hex[:12]


class _Formato(logging.Formatter):
    def __init__(self, como_json: bool):
        super().__init__()
        self.como_json = como_json

    def format(self, registro: logging.LogRecord) -> str:
        campos: dict = getattr(registro, "campos", {})
        quando = datetime.fromtimestamp(registro.created, timezone.utc).isoformat(timespec="milliseconds")
        mensagem = registro.getMessage()
        erro = self.formatException(registro.exc_info) if registro.exc_info else None
        if self.como_json:
            linha = {"quando": quando, "nivel": registro.levelname, "origem": registro.name,
                     "id": id_da_requisicao.get(), "mensagem": mensagem, **campos}
            if erro:
                linha["erro"] = erro
            return json.dumps(linha, ensure_ascii=False, default=str)
        extras = " ".join(f"{chave}={valor}" for chave, valor in campos.items())
        texto = f"{quando} {registro.levelname:<7} {registro.name} id={id_da_requisicao.get()} {mensagem}"
        if extras:
            texto += f" {extras}"
        return f"{texto}\n{erro}" if erro else texto


def configurar() -> None:
    """Liga os logs da aplicação (logger `concept` e filhos). Pode ser chamada mais de uma vez."""
    logger = logging.getLogger(NOME_DO_LOGGER)
    nivel = os.environ.get("LOG_NIVEL", "INFO").strip().upper()
    logger.setLevel(nivel if nivel in ("DEBUG", "INFO", "WARNING", "ERROR") else "INFO")
    como_json = os.environ.get("LOG_FORMATO", "texto").strip().lower() == "json"
    for antigo in [h for h in logger.handlers if getattr(h, "_do_concept", False)]:
        logger.removeHandler(antigo)
        antigo.close()
    formato = _Formato(como_json)
    destinos: list[logging.Handler] = [logging.StreamHandler()]
    if caminho := os.environ.get("LOG_ARQUIVO", "").strip():
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        destinos.append(RotatingFileHandler(
            caminho, maxBytes=_inteiro("LOG_ARQUIVO_MB", 5) * 1024 * 1024,
            backupCount=_inteiro("LOG_ARQUIVO_COPIAS", 5), encoding="utf-8"))
    for destino in destinos:
        destino._do_concept = True  # type: ignore[attr-defined]
        destino.setFormatter(formato)
        logger.addHandler(destino)


def _inteiro(nome: str, padrao: int) -> int:
    try:
        return max(1, int(os.environ.get(nome, padrao)))
    except ValueError:
        return padrao
