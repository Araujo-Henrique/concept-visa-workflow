"""Idempotência: o mesmo pedido de criação, reenviado com a mesma Idempotency-Key, vale uma vez só.

Cada teste prova uma promessa do módulo app/idempotencia.py (veja a lista no topo dele).
"""
import hashlib
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import db
from app.main import app
from app.models import ChaveIdempotencia, Cliente, Evento
from app.seguranca import criar_token
from app.servicos.usuarios import criar_usuario
from tests.conftest import novo_obt

CHAVE = "chave-de-teste-0001"


def _post(c, caminho, corpo, chave=CHAVE, **extra):
    cabecalhos = {"Idempotency-Key": chave} if chave else {}
    return c.post(caminho, json=corpo, headers=cabecalhos, **extra)


def _total(sessao, modelo):
    sessao.expire_all()
    return sessao.scalar(select(func.count()).select_from(modelo))


def test_reenvio_com_a_mesma_chave_devolve_a_mesma_resposta_sem_criar_de_novo(client, sessao):
    primeira = _post(client, "/clientes", {"nome": "Ana Souza"})
    segunda = _post(client, "/clientes", {"nome": "Ana Souza"})
    assert primeira.status_code == segunda.status_code == 201
    assert segunda.json() == primeira.json()  # o mesmo id: nada novo foi criado
    assert "Idempotent-Replayed" not in primeira.headers
    assert segunda.headers["Idempotent-Replayed"] == "true"
    assert _total(sessao, Cliente) == 1


def test_sem_a_chave_nada_muda(client, sessao):
    # a chave é opcional: quem não manda continua com o comportamento de antes
    assert _post(client, "/clientes", {"nome": "Ana Souza"}, chave=None).status_code == 201
    assert _post(client, "/clientes", {"nome": "Bia Souza"}, chave=None).status_code == 201
    assert _total(sessao, ChaveIdempotencia) == 0


def test_chaves_diferentes_sao_pedidos_diferentes(client, sessao):
    assert _post(client, "/clientes", {"nome": "Ana Souza"}, chave="chave-aaaaaaaa").status_code == 201
    assert _post(client, "/clientes", {"nome": "Bia Souza"}, chave="chave-bbbbbbbb").status_code == 201
    assert _total(sessao, Cliente) == 2


def test_mesma_chave_com_dados_diferentes_e_recusada(client, sessao):
    _post(client, "/clientes", {"nome": "Ana Souza"})
    outra = _post(client, "/clientes", {"nome": "Bia Souza"})
    assert outra.status_code == 422
    assert "já foi usada" in outra.json()["detail"]
    assert _total(sessao, Cliente) == 1  # a "Bia" não foi criada nem recebeu a resposta da Ana


def test_mesma_chave_em_outra_rota_e_recusada(client, sessao):
    _post(client, "/clientes", {"nome": "Ana Souza"})
    outra = _post(client, "/usuarios", {"nome": "Ana Souza"})
    assert outra.status_code == 422 and "já foi usada" in outra.json()["detail"]


def test_erro_nao_fica_guardado_a_pessoa_corrige_e_tenta_com_a_mesma_chave(client, sessao):
    erro = _post(client, "/clientes", {"nome": ""})  # dado inválido
    assert erro.status_code == 422
    assert _total(sessao, ChaveIdempotencia) == 0  # a chave foi liberada
    certo = _post(client, "/clientes", {"nome": "Ana Souza"})
    assert certo.status_code == 201 and "Idempotent-Replayed" not in certo.headers


def test_erro_de_regra_do_banco_tambem_libera_a_chave(client, sessao):
    _post(client, "/clientes", {"nome": "Ana Souza"}, chave="chave-aaaaaaaa")
    duplicado = _post(client, "/clientes", {"nome": "ana souza"}, chave="chave-bbbbbbbb")  # nome único
    assert duplicado.status_code == 409
    assert _total(sessao, ChaveIdempotencia) == 1  # só a do sucesso


def test_a_mesma_chave_de_outro_usuario_e_independente(client, sessao):
    outro = criar_usuario(sessao, "Outro Admin", "outro@exemplo.com", "admin", "senha-de-outro-123")
    sessao.commit()
    c2 = TestClient(app)
    c2.headers["Authorization"] = f"Bearer {criar_token(outro.id)}"
    a = _post(client, "/clientes", {"nome": "Ana Souza"})
    b = _post(c2, "/clientes", {"nome": "Bia Souza"})
    assert a.status_code == b.status_code == 201 and "Idempotent-Replayed" not in b.headers


@pytest.mark.parametrize("ruim", ["curta", "x" * 81, "com espaco aqui", "simbolo-@-1234567"])
def test_chave_mal_formada_e_recusada(client, ruim):
    resposta = _post(client, "/clientes", {"nome": "Ana Souza"}, chave=ruim)
    assert resposta.status_code == 422 and "Idempotency-Key" in resposta.json()["detail"]


def test_sem_login_continua_401_e_nao_reserva_nada(client_anonimo, sessao):
    resposta = _post(client_anonimo, "/clientes", {"nome": "Ana Souza"})
    assert resposta.status_code == 401
    assert _total(sessao, ChaveIdempotencia) == 0


def test_login_ignora_a_chave_para_nao_guardar_token(client_anonimo, usuario_teste, sessao):
    corpo = {"email": "teste@exemplo.com", "senha": "senha-de-teste-123"}
    a = _post(client_anonimo, "/auth/login", corpo)
    b = _post(client_anonimo, "/auth/login", corpo)
    assert a.status_code == b.status_code == 200
    assert "Idempotent-Replayed" not in b.headers
    assert _total(sessao, ChaveIdempotencia) == 0  # nenhuma resposta com token foi guardada


def test_reenviar_a_mudanca_de_situacao_nao_cria_segundo_evento(client, sessao, cliente):
    processo = novo_obt(cliente)
    sessao.add(processo)
    sessao.commit()
    url = f"/processos/{processo.id}/situacao"
    a = _post(client, url, {"situacao": "Pago"})
    b = _post(client, url, {"situacao": "Pago"})  # sem a chave seria 409 ("já está em Pago")
    assert a.status_code == b.status_code == 200 and b.json() == a.json()
    assert b.headers["Idempotent-Replayed"] == "true"
    assert _total(sessao, Evento) == 1


def test_resposta_vazia_204_tambem_e_repetida(client, sessao):
    alvo = criar_usuario(sessao, "Alvo", "alvo@exemplo.com", "admin", "senha-do-alvo-1234")
    sessao.commit()
    url = f"/usuarios/{alvo.id}/senha"
    a = _post(client, url, {"senha": "nova-senha-bem-longa-9"})
    b = _post(client, url, {"senha": "nova-senha-bem-longa-9"})
    assert a.status_code == b.status_code == 204
    assert b.headers["Idempotent-Replayed"] == "true"


def test_a_senha_do_pedido_nao_e_guardada(client, sessao):
    alvo = criar_usuario(sessao, "Alvo", "alvo@exemplo.com", "admin", "senha-do-alvo-1234")
    sessao.commit()
    _post(client, f"/usuarios/{alvo.id}/senha", {"senha": "nova-senha-bem-longa-9"})
    sessao.expire_all()
    linha = sessao.scalars(select(ChaveIdempotencia)).one()
    # só o sha256 do corpo é guardado, nunca o pedido
    assert "nova-senha" not in f"{linha.impressao} {linha.corpo} {linha.escopo}"


# ---------------------------------------------------------------- pedidos simultâneos e reservas velhas

def _reserva(client, sessao, usuario, **campos):
    """Simula a reserva de outro pedido igual ao que o client vai enviar (por padrão, ainda sem resposta).
    A impressão é calculada sobre os bytes reais que o httpx envia."""
    corpo = client.build_request("POST", "/clientes", json={"nome": "Ana Souza"}).content
    sessao.add(ChaveIdempotencia(usuario_id=usuario.id, chave=CHAVE, escopo="POST /clientes",
                                 impressao=hashlib.sha256(corpo).hexdigest(), **campos))
    sessao.commit()


def test_reenvio_durante_o_processamento_espera_e_devolve_o_resultado(client, sessao, usuario_teste, monkeypatch):
    _reserva(client, sessao, usuario_teste)

    def terminar_o_primeiro():
        time.sleep(0.6)
        with db.Session() as s:
            linha = s.scalars(select(ChaveIdempotencia)).one()
            linha.status, linha.corpo = 201, '{"id": 77, "nome": "Ana Souza"}'
            s.commit()

    fio = threading.Thread(target=terminar_o_primeiro)
    fio.start()
    inicio = time.monotonic()
    resposta = _post(client, "/clientes", {"nome": "Ana Souza"})
    fio.join()
    assert time.monotonic() - inicio >= 0.5  # esperou o primeiro terminar
    assert resposta.status_code == 201 and resposta.json()["id"] == 77
    assert resposta.headers["Idempotent-Replayed"] == "true"
    assert _total(sessao, Cliente) == 0  # esperou em vez de executar de novo


def test_espera_longa_demais_vira_409_com_retry_after(client, sessao, usuario_teste, monkeypatch):
    monkeypatch.setenv("IDEMPOTENCIA_ESPERA_SEGUNDOS", "0.4")
    _reserva(client, sessao, usuario_teste)
    resposta = _post(client, "/clientes", {"nome": "Ana Souza"})
    assert resposta.status_code == 409 and resposta.headers["Retry-After"] == "2"


def test_reserva_abandonada_ha_mais_de_um_minuto_deixa_o_pedido_executar(client, sessao, usuario_teste):
    _reserva(client, sessao, usuario_teste, criado_em=datetime.now(timezone.utc) - timedelta(minutes=5))
    resposta = _post(client, "/clientes", {"nome": "Ana Souza"})
    assert resposta.status_code == 201 and "Idempotent-Replayed" not in resposta.headers
    assert _total(sessao, Cliente) == 1


def test_chaves_com_mais_de_24h_sao_apagadas(client, sessao, usuario_teste):
    sessao.add(ChaveIdempotencia(
        usuario_id=usuario_teste.id, chave="chave-velha-001", escopo="POST /clientes", impressao="x", status=201,
        corpo="{}", criado_em=datetime.now(timezone.utc) - timedelta(hours=25)))
    sessao.commit()
    _post(client, "/clientes", {"nome": "Ana Souza"})
    sessao.expire_all()
    chaves = set(sessao.scalars(select(ChaveIdempotencia.chave)))
    assert chaves == {CHAVE}


def test_duplo_clique_de_verdade_dois_pedidos_ao_mesmo_tempo_criam_um_so(client, sessao, usuario_teste):
    resultados = []
    clientes = []
    for _ in range(2):
        c = TestClient(app)
        c.headers["Authorization"] = client.headers["Authorization"]
        clientes.append(c)

    def enviar(c):
        resultados.append(_post(c, "/clientes", {"nome": "Ana Souza"}))

    fios = [threading.Thread(target=enviar, args=(c,)) for c in clientes]
    for f in fios:
        f.start()
    for f in fios:
        f.join()
    assert sorted(r.status_code for r in resultados) == [201, 201]
    assert resultados[0].json()["id"] == resultados[1].json()["id"]
    assert _total(sessao, Cliente) == 1


def test_rota_que_devolve_4xx_sem_levantar_excecao_tambem_nao_guarda_o_erro(client, sessao):
    # as rotas de hoje sinalizam erro por exceção; isto protege uma rota futura que devolva a resposta direto
    from fastapi import APIRouter, FastAPI
    from fastapi.responses import JSONResponse
    from app.idempotencia import RotaIdempotente

    roteador = APIRouter(route_class=RotaIdempotente)

    @roteador.post("/teste-4xx")
    def devolve_erro():
        return JSONResponse(status_code=404, content={"detail": "nao achei"})

    mini = FastAPI()
    mini.include_router(roteador)
    c = TestClient(mini)
    c.headers["Authorization"] = client.headers["Authorization"]
    assert _post(c, "/teste-4xx", {"a": 1}).status_code == 404
    assert _total(sessao, ChaveIdempotencia) == 0
