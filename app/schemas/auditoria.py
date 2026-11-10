from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

TabelaAuditada = Literal["clientes", "processos", "processo_obt", "processo_ren", "processo_pass", "solicitantes",
                         "formularios_ds160"]
Acao = Literal["criou", "editou", "apagou"]


class AlteracaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tabela: str
    registro_id: int
    processo_id: int | None
    cliente_id: int | None
    acao: str
    antes: dict | None
    depois: dict | None
    usuario_id: int | None
    usuario_nome: str | None = None
    requisicao: str | None
    origem: str
    transacao: int
    criado_em: datetime
