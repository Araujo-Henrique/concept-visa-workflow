"""Datas no fuso de Brasília: o servidor roda em UTC, mas "hoje" é o dia de quem usa o sistema."""
from datetime import date, datetime, timezone

import pytest

from app import tempo
from app.tempo import hoje_em_sp
from tests.test_api import novo_cliente


@pytest.mark.parametrize("utc,esperado", [
    ("2026-11-10T02:30:00+00:00", date(2026, 11, 9)),   # 23h30 de 09/11 em Brasília: o UTC já virou o dia 10
    ("2026-11-10T02:59:59+00:00", date(2026, 11, 9)),   # último segundo do dia 09 em Brasília
    ("2026-11-10T03:00:00+00:00", date(2026, 11, 10)),  # meia-noite em Brasília
    ("2026-11-10T15:00:00+00:00", date(2026, 11, 10)),
    ("2027-01-01T01:00:00+00:00", date(2026, 12, 31)),  # virada de ano
])
def test_hoje_em_sp_acompanha_o_relogio_de_brasilia(utc, esperado):
    assert hoje_em_sp(datetime.fromisoformat(utc)) == esperado


def test_hoje_em_sp_sem_argumento_usa_o_relogio_de_agora():
    agora = datetime.now(timezone.utc)
    assert abs((hoje_em_sp() - agora.date()).days) <= 1
    assert tempo.FUSO.key == "America/Sao_Paulo"


def test_despacho_de_amanha_em_sp_e_recusado_mesmo_quando_o_utc_ja_virou_o_dia(client, monkeypatch):
    """22h30 de 09/11 em Brasília = 01h30 de 10/11 em UTC. `date.today()` (UTC) diria que 10/11 é hoje e aceitaria
    um despacho 'de amanhã'; em Brasília, 10/11 ainda é futuro."""
    monkeypatch.setattr("app.schemas.processo.hoje_em_sp", lambda: date(2026, 11, 9))
    ren = client.post("/processos-ren", json={"cliente_id": novo_cliente(client)["id"], "situacao": "Cadastro"}).json()
    url = f"/processos-ren/{ren['id']}"
    assert client.patch(url, json={"despachado_em": "2026-11-10"}).status_code == 422  # amanhã (SP)
    assert client.patch(url, json={"despachado_em": "2026-11-09"}).status_code == 200  # hoje (SP)
