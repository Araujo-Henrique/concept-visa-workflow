from typing import Annotated

from pydantic import ConfigDict, StringConstraints, create_model

Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def atualizacao(base: type, nome: str) -> type:
    """Cria a versão de PATCH de um schema: os mesmos campos, todos opcionais.

    O PATCH só diz o que mudou. A regra de verdade continua no schema base: a rota junta o que já está
    gravado com o que chegou e valida o resultado inteiro (ver routers/comum.py:aplicar_patch).
    """
    campos = {n: (campo.annotation | None, None) for n, campo in base.model_fields.items()}
    return create_model(nome, __config__=ConfigDict(extra="forbid"), **campos)
