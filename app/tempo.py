"""Datas no fuso de Brasília.

O servidor (e o contêiner Docker) roda em UTC: `date.today()` vira o dia seguinte às 21h de Brasília. As regras
de negócio ("a data do despacho não pode ser no futuro") valem para o dia de quem usa o sistema, então usam
`hoje_em_sp()`. O front faz o mesmo (hojeEmSP).
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")  # precisa do pacote tzdata (requirements.txt): o Windows e a imagem slim não trazem


def hoje_em_sp(agora: datetime | None = None) -> date:
    """O dia de hoje em Brasília. `agora` (com fuso) existe para os testes."""
    return (agora or datetime.now(timezone.utc)).astimezone(FUSO).date()
