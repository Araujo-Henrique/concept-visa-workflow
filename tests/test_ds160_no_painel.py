"""Painel: a coluna do DS-160 mostra o status MENOS avançado do processo (o gargalo) e quantos já estão fechados."""
from itertools import combinations_with_replacement

import pytest

from app.enums import StatusDS
from tests.test_api import novo_cliente, novo_obt

ORDEM = [s.value for s in StatusDS]  # Pendente < Parcial < Aberto < Preenchido < Revisado < Fechado
_contador = iter(range(100000, 999999))


def novo_codigo():
    return f"AA00{next(_contador):06d}"


def com_forms(client, *status, pessoas=1, tipo="obt"):
    """Cria um processo com um formulário para cada status, distribuídos entre `pessoas` pessoas."""
    cliente = novo_cliente(client, f"Cliente {next(_contador)}")
    if tipo == "obt":
        proc = novo_obt(client, cliente["id"])
    else:
        proc = client.post(f"/processos-{tipo}", json={"cliente_id": cliente["id"], "situacao": "Cadastro"}).json()
    ids = [s["id"] for s in proc["solicitantes"]]
    for i in range(1, pessoas):
        ids.append(client.post(f"/processos/{proc['id']}/solicitantes", json={"nome": f"Filho {i}"}).json()["id"])
    for i, st in enumerate(status):
        r = client.post(f"/solicitantes/{ids[i % len(ids)]}/formularios-ds160",
                        json={"codigo": novo_codigo(), "status": st})
        assert r.status_code == 201, r.text
    return proc["id"]


def linha(client, processo_id):
    return client.get("/painel", params={"processo_id": processo_id}).json()[0]


def test_sem_formulario_nao_ha_status(client):
    achada = linha(client, com_forms(client))
    assert achada["ds160_status"] is None and achada["ds160_fechados"] == 0 and achada["n_formularios"] == 0


@pytest.mark.parametrize("status", ORDEM)
def test_um_formulario_mostra_o_proprio_status(client, status):
    """Roda por TODOS os status do enum: se um novo for criado e esquecido no CASE da view, este teste falha."""
    achada = linha(client, com_forms(client, status))
    assert achada["ds160_status"] == status
    assert achada["ds160_fechados"] == (1 if status == "Fechado" else 0)


@pytest.mark.parametrize("par", list(combinations_with_replacement(ORDEM, 2)), ids="-".join)
def test_com_dois_formularios_vale_o_menos_avancado(client, par):
    """Todos os pares possíveis, nas duas ordens de cadastro: a view ordena como o enum, não como o texto."""
    esperado = min(par, key=ORDEM.index)
    for ordem in (par, par[::-1]):
        achada = linha(client, com_forms(client, *ordem, pessoas=2))
        assert achada["ds160_status"] == esperado
        assert achada["ds160_fechados"] == sum(s == "Fechado" for s in par)
        assert achada["n_formularios"] == 2


def test_so_fica_fechado_quando_todos_estao_fechados(client):
    pid = com_forms(client, "Fechado", "Fechado", "Aberto", pessoas=3)
    achada = linha(client, pid)
    assert (achada["ds160_status"], achada["ds160_fechados"], achada["n_formularios"]) == ("Aberto", 2, 3)
    assert achada["n_solicitantes"] == 3


def test_mais_de_um_formulario_da_mesma_pessoa_tambem_conta(client):
    achada = linha(client, com_forms(client, "Revisado", "Fechado", "Preenchido", pessoas=1))
    assert (achada["ds160_status"], achada["ds160_fechados"], achada["n_formularios"]) == ("Preenchido", 1, 3)


def test_pessoa_sem_formulario_nao_entra_na_conta_mas_aparece_na_diferenca(client):
    """3 pessoas e 1 formulário: o painel diz n_formularios=1 e n_solicitantes=3 (a tela mostra 'faltam 2')."""
    achada = linha(client, com_forms(client, "Fechado", pessoas=3))
    assert (achada["ds160_status"], achada["n_formularios"], achada["n_solicitantes"]) == ("Fechado", 1, 3)


def test_mudar_o_status_do_formulario_muda_o_painel(client):
    pid = com_forms(client, "Aberto", "Fechado", pessoas=2)
    assert linha(client, pid)["ds160_status"] == "Aberto"
    aberto = next(f for s in client.get(f"/processos-obt/{pid}").json()["solicitantes"] for f in s["formularios"]
                  if f["status"] == "Aberto")
    client.patch(f"/formularios-ds160/{aberto['id']}", json={"status": "Fechado"})
    achada = linha(client, pid)
    assert (achada["ds160_status"], achada["ds160_fechados"]) == ("Fechado", 2)


def test_renovacao_tambem_mostra_o_ds160(client):
    achada = linha(client, com_forms(client, "Parcial", "Revisado", pessoas=2, tipo="ren"))
    assert achada["tipo"] == "REN" and achada["ds160_status"] == "Parcial" and achada["ds160_fechados"] == 0


def test_passaporte_nao_tem_coluna_de_ds160(client):
    cliente = novo_cliente(client)
    client.post("/processos-pass", json={"cliente_id": cliente["id"], "situacao": "Pendente"})
    achada = client.get("/painel", params={"tipo": "PASS"}).json()[0]
    assert "ds160_status" not in achada and "ds160_fechados" not in achada


def test_o_painel_nao_duplica_processos_com_varias_pessoas_e_formularios(client):
    pid = com_forms(client, "Aberto", "Fechado", "Revisado", pessoas=3)
    achadas = client.get("/painel", params={"processo_id": pid}).json()
    assert len(achadas) == 1 and achadas[0]["n_solicitantes"] == 3 and achadas[0]["n_formularios"] == 3


# ---------------------------------------------------------------- filtro por status do DS-160

def ids(client, **params):
    return sorted(l["processo_id"] for l in client.get("/painel", params={"limit": 200, **params}).json())


def test_filtra_pelo_status_que_a_coluna_mostra(client):
    pendente = com_forms(client, "Pendente")
    aberto = com_forms(client, "Aberto")
    misto = com_forms(client, "Fechado", "Aberto", pessoas=2)       # a coluna mostra "Aberto" (o menos avançado)
    fechado = com_forms(client, "Fechado", "Fechado", pessoas=2)
    assert ids(client, ds160="Aberto") == sorted([aberto, misto])
    assert ids(client, ds160="Fechado") == [fechado]
    assert ids(client, ds160="Pendente") == [pendente]
    assert ids(client, ds160="Revisado") == []


@pytest.mark.parametrize("status", ORDEM)
def test_cada_status_do_enum_pode_ser_filtrado(client, status):
    pid = com_forms(client, status)
    com_forms(client, "Fechado" if status != "Fechado" else "Pendente")
    assert ids(client, ds160=status) == [pid]


def test_sem_pega_quem_nao_tem_nenhum_formulario(client):
    sem = com_forms(client)
    com_forms(client, "Aberto")
    assert ids(client, ds160="sem", tipo="OBT") == [sem]


def test_filtro_do_ds160_combina_com_os_outros_e_o_total_acompanha(client):
    obt_aberto = com_forms(client, "Aberto")
    com_forms(client, "Aberto", tipo="ren")
    resposta = client.get("/painel", params={"ds160": "Aberto", "tipo": "OBT"})
    assert [l["processo_id"] for l in resposta.json()] == [obt_aberto]
    assert resposta.headers["X-Total-Count"] == "1"


def test_ds160_invalido_da_422_e_diz_os_valores(client):
    resposta = client.get("/painel", params={"ds160": "Inventado"})
    assert resposta.status_code == 422 and "Fechado" in resposta.json()["detail"] and "sem" in resposta.json()["detail"]
