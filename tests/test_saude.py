"""Health check: /saude (vivo) e /pronto (banco responde). Públicos, sem dados, sem limite por IP."""
import logging

import pytest
from sqlalchemy.exc import OperationalError

from app import db, limites


def test_saude_responde_sem_login_e_sem_tocar_no_banco(client_anonimo, monkeypatch):
    def banco_proibido(*a, **k):
        raise AssertionError("/saude não pode consultar o banco")
    monkeypatch.setattr(db, "Session", banco_proibido)
    resposta = client_anonimo.get("/saude")
    assert resposta.status_code == 200 and resposta.json() == {"status": "ok"}


def test_pronto_confere_o_banco(client_anonimo):
    resposta = client_anonimo.get("/pronto")
    assert resposta.status_code == 200 and resposta.json() == {"status": "ok"}


def test_pronto_com_banco_fora_responde_503_sem_vazar_o_motivo(client_anonimo, monkeypatch, caplog):
    def sem_banco():
        raise OperationalError("SELECT 1", {}, Exception("connection to server at 10.0.0.5 failed: senha-x"))
    monkeypatch.setattr(db, "Session", sem_banco)
    with caplog.at_level(logging.INFO, logger="concept"):
        resposta = client_anonimo.get("/pronto")
    assert resposta.status_code == 503 and resposta.json() == {"status": "indisponivel"}
    assert "10.0.0.5" not in resposta.text and "senha-x" not in resposta.text  # o detalhe fica só no log
    assert any("10.0.0.5" in str(r.exc_info[1]) for r in caplog.records if r.exc_info)


def test_nao_expoe_nada_alem_do_status(client_anonimo):
    for caminho in ("/saude", "/pronto"):
        assert set(client_anonimo.get(caminho).json()) == {"status"}


def test_monitoramento_nao_gasta_o_limite_por_ip(client_anonimo, monkeypatch):
    monkeypatch.setattr(limites, "geral", limites.Janela(3, 60))
    assert all(client_anonimo.get(c).status_code == 200 for c in ["/saude", "/pronto"] * 10)
    # o limite continua valendo para o resto, e a cota não foi gasta pelo monitor
    assert client_anonimo.get("/auth/eu").status_code == 401  # 1ª de 3 permitidas


def test_requisicao_de_saude_nao_polui_o_log_normal(client_anonimo, caplog):
    with caplog.at_level(logging.INFO, logger="concept"):
        client_anonimo.get("/saude")
        client_anonimo.get("/auth/eu")
    caminhos = [r.campos["caminho"] for r in caplog.records if getattr(r, "campos", None)]
    assert "/saude" not in caminhos and "/auth/eu" in caminhos


def test_saude_ainda_leva_o_codigo_da_requisicao(client_anonimo):
    assert client_anonimo.get("/saude").headers["X-Request-ID"]


@pytest.mark.parametrize("metodo", ["post", "delete", "put"])
def test_so_aceita_get(client_anonimo, metodo):
    assert getattr(client_anonimo, metodo)("/saude").status_code == 405
