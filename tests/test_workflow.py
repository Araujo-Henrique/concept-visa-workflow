import threading
import time

from sqlalchemy import select

from app import db
from app.models import Evento, Processo
from app.servicos.workflow import mudar_situacao
from tests.test_api import novo_cliente, novo_obt


def processo_obt(client, situacao="Processando"):
    cliente = novo_cliente(client)
    return novo_obt(client, cliente["id"], situacao=situacao)


def muda(client, processo_id, situacao, **extra):
    return client.post(f"/processos/{processo_id}/situacao", json={"situacao": situacao, **extra})


def test_mudar_situacao_grava_a_mudanca_e_o_evento(client):
    processo = processo_obt(client)
    resposta = muda(client, processo["id"], "Pago")
    assert resposta.status_code == 200
    evento = resposta.json()
    assert (evento["tipo"], evento["situacao_anterior"], evento["situacao_nova"]) == (
        "situacao_alterada", "Processando", "Pago")
    assert client.get(f"/processos-obt/{processo['id']}").json()["situacao"] == "Pago"


def test_historico_mostra_a_linha_do_tempo_em_ordem(client):
    processo = processo_obt(client)
    muda(client, processo["id"], "Pago")
    muda(client, processo["id"], "Concluido")
    linha = [(e["tipo"], e["situacao_anterior"], e["situacao_nova"])
             for e in client.get(f"/processos/{processo['id']}/eventos").json()]
    assert linha == [("criado", None, "Processando"),
                     ("situacao_alterada", "Processando", "Pago"),
                     ("situacao_alterada", "Pago", "Concluido")]


def test_situacao_invalida_para_o_tipo_da_422_e_nao_grava(client):
    processo = processo_obt(client)
    assert muda(client, processo["id"], "Pix").status_code == 422  # Pix só existe para passaporte
    assert muda(client, processo["id"], "Inventada").status_code == 422
    assert len(client.get(f"/processos/{processo['id']}/eventos").json()) == 1  # só o "criado"


def test_mesma_situacao_da_409(client):
    processo = processo_obt(client)
    assert muda(client, processo["id"], "Processando").status_code == 409


def test_processo_inexistente_da_404(client):
    assert muda(client, 999, "Pago").status_code == 404
    assert client.get("/processos/999/eventos").status_code == 404


def test_sair_de_concluido_exige_motivo(client):
    processo = processo_obt(client)
    muda(client, processo["id"], "Concluido")
    assert muda(client, processo["id"], "Processando").status_code == 422
    assert muda(client, processo["id"], "Processando", motivo="   ").status_code == 422
    # nada mudou: continua concluído e sem evento novo
    assert client.get(f"/processos-obt/{processo['id']}").json()["situacao"] == "Concluido"
    assert len(client.get(f"/processos/{processo['id']}/eventos").json()) == 2


def test_voltar_de_concluido_para_processando_e_permitido_com_motivo(client):
    processo = processo_obt(client)
    muda(client, processo["id"], "Concluido")
    resposta = muda(client, processo["id"], "Processando", motivo="Cliente vai tentar de novo")
    assert resposta.status_code == 200
    evento = resposta.json()
    assert evento["tipo"] == "reaberto" and evento["motivo"] == "Cliente vai tentar de novo"
    assert client.get(f"/processos-obt/{processo['id']}").json()["situacao"] == "Processando"


def test_workflow_vale_para_renovacao_e_passaporte(client):
    cliente = novo_cliente(client)
    ren = client.post("/processos-ren", json={"cliente_id": cliente["id"], "situacao": "Cadastro"}).json()
    pas = client.post("/processos-pass", json={"cliente_id": cliente["id"], "situacao": "Pendente"}).json()
    assert muda(client, ren["id"], "Entrevista").status_code == 200  # só existe em renovação
    assert muda(client, pas["id"], "Pix").status_code == 200  # só existe em passaporte
    assert muda(client, pas["id"], "Entrevista").status_code == 422


def test_motivo_e_opcional_em_mudanca_comum_e_fica_registrado(client):
    processo = processo_obt(client)
    evento = muda(client, processo["id"], "Pago", motivo="Pagamento confirmado").json()
    assert evento["motivo"] == "Pagamento confirmado"


def test_mudancas_simultaneas_viram_fila_e_o_historico_fica_coerente(client, sessao):
    """Duas pessoas mudam o mesmo processo ao mesmo tempo. Com a trava (FOR UPDATE), a segunda espera
    a primeira e registra a situação que de fato era a anterior; sem a trava, as duas leriam 'Processando'."""
    processo = processo_obt(client)
    pid = processo["id"]
    segunda_terminou = threading.Event()

    def segunda_pessoa():
        with db.Session() as s2:
            mudar_situacao(s2, pid, "Concluido")
            s2.commit()
        segunda_terminou.set()

    with db.Session() as s1:
        mudar_situacao(s1, pid, "Pago")  # primeira pessoa: tem a linha travada, ainda sem commit
        thread = threading.Thread(target=segunda_pessoa)
        thread.start()
        time.sleep(0.7)
        assert not segunda_terminou.is_set()  # a segunda está esperando
        s1.commit()  # libera a trava
    assert segunda_terminou.wait(timeout=10)
    thread.join()

    with db.Session() as leitura:
        eventos = leitura.scalars(select(Evento).where(Evento.processo_id == pid).order_by(Evento.id)).all()
        assert [(e.situacao_anterior, e.situacao_nova) for e in eventos] == [
            (None, "Processando"), ("Processando", "Pago"), ("Pago", "Concluido")]
        assert leitura.get(Processo, pid).situacao == "Concluido"
