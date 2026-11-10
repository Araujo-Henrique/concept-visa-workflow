from typing import Annotated

from pydantic import ConfigDict, StringConstraints, create_model

def texto(maximo: int):
    """Texto sem espaços nas pontas, não vazio e com TAMANHO MÁXIMO. O máximo acompanha a coluna do banco: sem
    ele, um valor grande passaria pela validação e o Postgres o recusaria no INSERT (erro 500 e dado do cliente
    no log). A regra vale na entrada; dados antigos nunca passam do tamanho da própria coluna."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=maximo)]


Texto = texto(200)  # nome e e-mail (colunas de 200)
# Quantas pessoas (titular + extras) um processo pode ter. Sem teto, uma única requisição criaria centenas de milhares
# de linhas (e de linhas de auditoria, que não se apagam) e deixaria as listagens pesadas para todo mundo.
MAX_PESSOAS_POR_PROCESSO = 50
# Colunas de texto livre (Text no banco): sem máximo próprio; o limite é o teto de corpo da requisição.
TextoLivre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def atualizacao(base: type, nome: str) -> type:
    """Cria a versão de PATCH de um schema: os mesmos campos, todos opcionais.

    O PATCH só diz o que mudou. A regra de verdade continua no schema base: a rota junta o que já está
    gravado com o que chegou e valida o resultado inteiro (ver routers/comum.py:aplicar_patch).
    """
    campos = {n: (campo.annotation | None, None) for n, campo in base.model_fields.items()}
    return create_model(nome, __config__=ConfigDict(extra="forbid"), **campos)
