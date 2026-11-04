from datetime import date, datetime

from pydantic import BaseModel


class PainelOut(BaseModel):
    """Uma linha por processo, como na planilha: quem é, quantos são, onde está e como está."""
    processo_id: int
    tipo: str
    situacao: str
    cliente_id: int
    cliente: str
    telefone: str | None
    grupo: str | None
    titular: str | None
    n_solicitantes: int
    solicitantes: str  # nomes separados por vírgula, titular primeiro
    resultado_geral: str  # Processando, Aprovado, Negado ou Parcial (resultados diferentes)
    n_formularios: int
    consulado: str | None
    data_casv: date | None
    data_entrevista: date | None
    data_despacho: date | None
    data_pf: date | None
    prazo_pf: date | None
    codigo_rastreio: str | None
    atualizado_em: datetime
