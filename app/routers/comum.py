from fastapi import HTTPException
from pydantic import BaseModel, ValidationError


def obter_ou_404(sessao, modelo, id: int, rotulo: str):
    objeto = sessao.get(modelo, id)
    if objeto is None:
        raise HTTPException(status_code=404, detail=f"{rotulo} não encontrado")
    return objeto


def aplicar_patch(base: type[BaseModel], objeto, patch: dict) -> None:
    """Aplica um PATCH sem deixar o registro inválido.

    Junta o que já está gravado com o que chegou, valida o resultado inteiro no schema base
    (assim as regras entre campos valem também na edição) e só então grava no objeto.
    """
    atual = {campo: getattr(objeto, campo) for campo in base.model_fields}
    atual.update(patch)
    try:
        # o contexto diz quais campos o PATCH trouxe: regras de dados antigos só valem se a edição os toca
        validado = base.model_validate(atual, context={"alterados": set(patch)})
    except ValidationError as erro:
        raise HTTPException(
            status_code=422, detail=erro.errors(include_url=False, include_context=False, include_input=False))
    for campo in patch:
        setattr(objeto, campo, getattr(validado, campo))
