"""O que cada perfil pode fazer.

Cinco permissões, escolhidas pelo método HTTP da requisição (regra única, aplicada em app/main.py):
  ler            GET
  escrever       POST e PATCH
  apagar         DELETE (processo, pessoa, DS-160: só admin)
  apagar_cliente DELETE /clientes/{id}: admin e atendente. Pode ficar com o atendente porque excluir um cliente
                 não perde nada: o admin restaura pela auditoria (e só ele elimina de vez).
  administrar    gerenciar usuários, auditoria, restauração e eliminação (exigem esta permissão explicitamente)

Um perfil que não esteja aqui não pode nada (nega por padrão).
"""
LER, ESCREVER, APAGAR, APAGAR_CLIENTE, ADMINISTRAR = "ler", "escrever", "apagar", "apagar_cliente", "administrar"

PERMISSOES: dict[str, frozenset[str]] = {
    "admin": frozenset({LER, ESCREVER, APAGAR, APAGAR_CLIENTE, ADMINISTRAR}),
    "atendente": frozenset({LER, ESCREVER, APAGAR_CLIENTE}),
    "leitor": frozenset({LER}),
}

_POR_METODO = {"GET": LER, "HEAD": LER, "DELETE": APAGAR}


# o DELETE destas rotas (o padrão de caminho como o FastAPI o declara) exige só `apagar_cliente`
_DELETE_DE_CLIENTE = {"/clientes/{cliente_id}"}


def exigida_pelo_metodo(metodo: str, rota: str | None = None) -> str:
    """GET lê, DELETE apaga e qualquer outro método (POST, PATCH, PUT) escreve. `rota` é o caminho declarado
    (ex.: "/clientes/{cliente_id}"): o DELETE de cliente tem a sua própria permissão."""
    if metodo.upper() == "DELETE" and rota in _DELETE_DE_CLIENTE:
        return APAGAR_CLIENTE
    return _POR_METODO.get(metodo.upper(), ESCREVER)


def pode(perfil: str, permissao: str) -> bool:
    return permissao in PERMISSOES.get(perfil, frozenset())
