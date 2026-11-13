"""Painel: ordem "agenda" (a da tela de processos): primeiro os com data marcada, da mais próxima para a mais distante."""
from datetime import date

import pytest

from tests.test_api import novo_cliente, novo_obt

HOJE = date(2026, 11, 10)


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    monkeypatch.setattr("app.routers.painel.hoje_em_sp", lambda: HOJE)


def obt(client, cliente, **campos):
    campos.setdefault("consulado", "SP")
    return novo_obt(client, cliente["id"], **campos)["id"]


def ren(client, cliente, **campos):
    r = client.post("/processos-ren", json={"cliente_id": cliente["id"], "situacao": "Cadastro", **campos})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def passaporte(client, cliente, **campos):
    r = client.post("/processos-pass", json={"cliente_id": cliente["id"], "situacao": "Pendente", **campos})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def ordem(client, **params):
    return [l["processo_id"] for l in client.get("/painel", params={"ordem": "agenda", "limit": 200, **params}).json()]


def test_data_mais_proxima_primeiro_e_hoje_conta(client):
    c = novo_cliente(client)
    longe = obt(client, c, data_casv="2026-12-20")
    perto = obt(client, c, data_casv="2026-11-12")
    hoje = obt(client, c, data_casv="2026-11-10")  # hoje ainda é "de hoje em diante"
    assert ordem(client, tipo="OBT") == [hoje, perto, longe]


def test_sem_data_ou_com_data_passada_ficam_depois_dos_mais_novos_para_os_mais_antigos(client):
    c = novo_cliente(client)
    passada = obt(client, c, data_casv="2026-11-01")
    sem_data = obt(client, c)
    futura = obt(client, c, data_casv="2027-03-01")
    outra_sem_data = obt(client, c)
    # com data marcada primeiro; o resto, do processo mais novo para o mais antigo
    assert ordem(client, tipo="OBT") == [futura, outra_sem_data, sem_data, passada]


def test_vale_a_menor_data_entre_casv_e_entrevista(client):
    c = novo_cliente(client)
    so_casv = obt(client, c, data_casv="2026-11-20")
    entrevista_antes = obt(client, c, data_casv="2026-12-20", data_entrevista="2026-11-11")
    assert ordem(client, tipo="OBT") == [entrevista_antes, so_casv]


def test_data_ja_passada_nao_conta_a_futura_do_mesmo_processo_sim(client):
    c = novo_cliente(client)
    a = obt(client, c, data_casv="2026-12-20", data_entrevista="2026-11-01")  # entrevista passou: vale o CASV
    b = obt(client, c, data_casv="2026-11-25")
    assert ordem(client, tipo="OBT") == [b, a]


def test_a_previsao_da_orientacao_nao_conta_como_data_marcada(client):
    c = novo_cliente(client)
    com_previsao_cedo = obt(client, c, data_casv="2026-11-30")  # previsão 16/11: é só uma conta
    casv_antes = obt(client, c, data_casv="2026-11-20")
    assert ordem(client, tipo="OBT") == [casv_antes, com_previsao_cedo]


def test_orientacao_conta_so_quando_esta_agendada(client):
    c = novo_cliente(client)
    agendada = obt(client, c, data_casv="2026-12-30", orientacao="Agendada", orientacao_data="2026-11-14")
    feita = obt(client, c, data_casv="2026-12-29", orientacao="Fornecidas", orientacao_data="2026-11-11")
    casv_no_meio = obt(client, c, data_casv="2026-11-18")
    # a agendada (14/11) vem antes do CASV (18/11); a "Fornecidas" não conta a data da orientação: vale o CASV
    assert ordem(client, tipo="OBT") == [agendada, casv_no_meio, feita]


def test_despacho_conta_so_enquanto_falta_despachar(client):
    c = novo_cliente(client)
    falta = ren(client, c, consulado="SP", data_casv="2026-11-18")        # despacho 11/11
    feito = ren(client, c, consulado="SP", data_casv="2026-11-17", despachado_em="2026-11-09")  # prazo já cumprido
    # falta (despacho 11/11) vem primeiro; "feito" vale o CASV (17/11), que ainda não passou
    assert ordem(client, tipo="REN") == [falta, feito]
    depois = ren(client, c, consulado="SP", data_casv="2026-11-19", despachado_em="2026-11-09")
    assert ordem(client, tipo="REN") == [falta, feito, depois]


def test_passaporte_usa_pf_e_prazo(client):
    c = novo_cliente(client)
    pf_longe = passaporte(client, c, data_pf="2026-12-30")
    prazo_perto = passaporte(client, c, data_pf="2026-11-01", prazo_pf="2026-11-15")
    assert ordem(client, tipo="PASS") == [prazo_perto, pf_longe]


def test_misturando_tipos_a_data_mais_proxima_vence(client):
    c = novo_cliente(client)
    o = obt(client, c, data_casv="2026-11-30")
    r = ren(client, c, consulado="SP", data_casv="2026-11-14")          # despacho 07/11: já passou; vale o CASV 14/11
    p = passaporte(client, c, data_pf="2026-11-12")
    assert ordem(client) == [p, r, o]


def test_processo_concluido_nao_sobe_pela_data(client):
    c = novo_cliente(client)
    pendente = obt(client, c, data_casv="2026-12-20")
    concluido = obt(client, c, data_casv="2026-11-12", situacao="Concluido")  # data futura, mas já está concluído
    outro = obt(client, c, data_casv="2026-12-25")
    # o concluído vai para o grupo "sem prioridade" (mais novo primeiro), depois dos pendentes com data
    assert ordem(client, tipo="OBT") == [pendente, outro, concluido]


def test_a_ordem_vale_entre_as_paginas(client):
    c = novo_cliente(client)
    ids = [obt(client, c, data_casv=f"2026-12-{dia:02d}") for dia in (25, 11, 20, 15, 28)]
    esperado = [ids[1], ids[3], ids[2], ids[0], ids[4]]  # 11, 15, 20, 25, 28
    paginas = []
    for offset in (0, 2, 4):
        resposta = client.get("/painel", params={"tipo": "OBT", "ordem": "agenda", "limit": 2, "offset": offset})
        assert resposta.headers["X-Total-Count"] == "5"
        paginas += [l["processo_id"] for l in resposta.json()]
    assert paginas == esperado


def test_filtros_continuam_valendo_com_a_ordem(client):
    c = novo_cliente(client)
    a = obt(client, c, data_casv="2026-12-01", consulado="RIO")
    obt(client, c, data_casv="2026-11-12", consulado="SP")
    b = obt(client, c, data_casv="2026-12-05", consulado="RIO")
    assert ordem(client, tipo="OBT", consulado="RIO") == [a, b]


def test_sem_pedir_a_ordem_a_api_segue_com_os_mais_novos_primeiro(client):
    c = novo_cliente(client)
    primeiro = obt(client, c, data_casv="2026-11-12")
    segundo = obt(client, c, data_casv="2027-01-12")
    padrao = [l["processo_id"] for l in client.get("/painel", params={"tipo": "OBT"}).json()]
    assert padrao == [segundo, primeiro]  # compatível com quem já usa a API
    assert ordem(client, tipo="OBT") == [primeiro, segundo]


def test_ordem_invalida_da_422(client):
    assert client.get("/painel", params={"ordem": "aleatoria"}).status_code == 422


def test_sem_nenhum_processo_nao_quebra(client):
    assert ordem(client) == []
