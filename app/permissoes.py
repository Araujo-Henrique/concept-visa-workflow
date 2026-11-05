"""O que cada perfil pode fazer.

Quatro permissões, escolhidas pelo método HTTP da requisição (regra única, aplicada em app/main.py):
  ler         GET
  escrever    POST e PATCH
  apagar      DELETE
  administrar gerenciar usuários (rotas /usuarios, que exigem esta permissão explicitamente)

Um perfil que não esteja aqui não pode nada (nega por padrão).
"""
LER, ESCREVER, APAGAR, ADMINISTRAR = "ler", "escrever", "apagar", "administrar"

PERMISSOES: dict[str, frozenset[str]] = {
    "admin": frozenset({LER, ESCREVER, APAGAR, ADMINISTRAR}),
    "atendente": frozenset({LER, ESCREVER}),
    "leitor": frozenset({LER}),
}

_POR_METODO = {"GET": LER, "HEAD": LER, "DELETE": APAGAR}


def exigida_pelo_metodo(metodo: str) -> str:
    """GET lê, DELETE apaga e qualquer outro método (POST, PATCH, PUT) escreve."""
    return _POR_METODO.get(metodo.upper(), ESCREVER)


def pode(perfil: str, permissao: str) -> bool:
    return permissao in PERMISSOES.get(perfil, frozenset())
