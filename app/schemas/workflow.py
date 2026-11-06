from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.enums import TipoEvento
from app.schemas.comum import Texto


class MudarSituacao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    situacao: Texto
    motivo: Texto | None = None  # obrigatório ao sair de Concluído


class EventoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    processo_id: int
    usuario_id: int | None
    tipo: TipoEvento
    situacao_anterior: str | None
    situacao_nova: str | None
    motivo: str | None
    criado_em: datetime
    usuario_nome: str | None = None  # quem fez (vazio em eventos sem usuário, como os da importação)
