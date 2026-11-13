"""OBT: a previsão da orientação (2 semanas antes do CASV) é calculada pelo banco e NÃO mexe no status."""
import pytest

from tests.test_api import novo_cliente, novo_obt


@pytest.mark.parametrize("casv,previsao", [
    ("2026-12-15", "2026-12-01"),   # o exemplo do pedido: CASV dia 15, orientação dia 1
    ("2026-12-10", "2026-11-26"),   # vira o mês
    ("2027-01-05", "2026-12-22"),   # vira o ano
    ("2028-03-10", "2028-02-25"),   # ano bissexto (fevereiro de 29 dias)
    ("2027-03-10", "2027-02-24"),   # ano comum
])
def test_previsao_e_14_dias_antes_do_casv(client, casv, previsao):
    obt = novo_obt(client, novo_cliente(client)["id"], consulado="SP", data_casv=casv)
    assert obt["previsao_orientacao"] == previsao
    assert client.get(f"/processos-obt/{obt['id']}").json()["previsao_orientacao"] == previsao


def test_previsao_nao_muda_o_status_da_orientacao(client):
    obt = novo_obt(client, novo_cliente(client)["id"], consulado="SP", data_casv="2026-12-15")
    assert obt["orientacao"] == "Pendente" and obt["orientacao_data"] is None  # tem previsão e segue Pendente
    linha = client.get("/painel", params={"tipo": "OBT"}).json()[0]
    assert linha["previsao_orientacao"] == "2026-12-01" and linha["orientacao"] == "Pendente"


def test_sem_casv_nao_ha_previsao(client):
    obt = novo_obt(client, novo_cliente(client)["id"])
    assert obt["previsao_orientacao"] is None
    assert client.get("/painel", params={"tipo": "OBT"}).json()[0]["previsao_orientacao"] is None


def test_mudar_o_casv_recalcula_a_previsao_e_tirar_o_casv_apaga(client):
    obt = novo_obt(client, novo_cliente(client)["id"], consulado="SP", data_casv="2026-12-15")
    url = f"/processos-obt/{obt['id']}"
    assert client.patch(url, json={"data_casv": "2026-12-20"}).json()["previsao_orientacao"] == "2026-12-06"
    assert client.patch(url, json={"data_casv": None}).json()["previsao_orientacao"] is None


def test_orientacao_agendada_a_mao_nao_e_trocada_pela_previsao(client):
    obt = novo_obt(client, novo_cliente(client)["id"], consulado="SP", data_casv="2026-12-15",
                   orientacao="Agendada", orientacao_data="2026-12-03")
    assert obt["orientacao_data"] == "2026-12-03"        # a data real marcada continua sendo a marcada
    assert obt["previsao_orientacao"] == "2026-12-01"     # e a previsão segue sendo só a conta


def test_previsao_nao_pode_ser_gravada_pela_api(client):
    obt = novo_obt(client, novo_cliente(client)["id"], consulado="SP", data_casv="2026-12-15")
    recusa = client.patch(f"/processos-obt/{obt['id']}", json={"previsao_orientacao": "2026-11-01"})
    assert recusa.status_code == 422  # campo calculado: o schema de edição não o aceita


def test_so_o_obt_tem_previsao_de_orientacao(client):
    cliente = novo_cliente(client)
    client.post("/processos-ren", json={"cliente_id": cliente["id"], "situacao": "Cadastro",
                                        "consulado": "SP", "data_casv": "2026-12-15"})
    ren = next(l for l in client.get("/painel", params={"tipo": "REN"}).json())
    assert "previsao_orientacao" not in ren and ren["data_despacho"] == "2026-12-08"


def test_filtrar_pelo_periodo_da_previsao(client):
    cliente = novo_cliente(client)
    dentro = novo_obt(client, cliente["id"], consulado="SP", data_casv="2026-12-15")      # previsão 01/12
    novo_obt(client, cliente["id"], consulado="SP", data_casv="2027-02-15")               # previsão 01/02
    novo_obt(client, cliente["id"])                                                         # sem previsão
    achados = client.get("/painel", params={"tipo": "OBT", "data": "previsao_orientacao",
                                            "de": "2026-11-28", "ate": "2026-12-05"}).json()
    assert [a["processo_id"] for a in achados] == [dentro["id"]]


def test_a_previsao_nao_entra_na_agenda(client):
    novo_obt(client, novo_cliente(client)["id"], consulado="SP", data_casv="2026-12-15")
    eventos = client.get("/painel/agenda", params={"de": "2026-11-25", "ate": "2026-12-20"}).json()
    assert [e["evento"] for e in eventos] == ["casv"]  # a previsão é conta, não compromisso marcado
