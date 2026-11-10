"""Limites de requisições: login (por IP e por conta), troca de senha, limite geral e tamanho do corpo."""
import pytest
from fastapi import Request
from psycopg.errors import QueryCanceled
from sqlalchemy.exc import OperationalError

from app import limites
from tests.conftest import SENHA_TESTE


def login(c, email="teste@exemplo.com", senha=SENHA_TESTE, **kw):
    return c.post("/auth/login", json={"email": email, "senha": senha}, **kw)


class Relogio:
    def __init__(self):
        self.agora = 1000.0

    def __call__(self):
        return self.agora


# ---------------------------------------------------------------- a janela

def test_janela_conta_e_libera_quando_o_tempo_passa():
    relogio = Relogio()
    janela = limites.Janela(2, 60, relogio=relogio)
    assert janela.registrar("a") == 0 and janela.registrar("a") == 0
    assert janela.registrar("a") == 60  # cheia: espera a mais antiga sair
    assert janela.registrar("b") == 0  # cada chave conta por si
    relogio.agora += 30
    assert janela.espera("a") == 30
    relogio.agora += 30
    assert janela.espera("a") == 0 and janela.registrar("a") == 0


def test_janela_esquece_chaves_paradas():
    relogio = Relogio()
    janela = limites.Janela(5, 60, relogio=relogio)
    for i in range(100):
        janela.registrar(f"ip-{i}")
    relogio.agora += 61
    janela.registrar("novo")
    assert list(janela._marcas) == ["novo"]


@pytest.mark.parametrize("segundos,texto", [(30, "30 segundos"), (60, "1 minuto"), (61, "2 minutos"),
                                            (900, "15 minutos")])
def test_mensagem_de_espera(segundos, texto):
    assert limites.mensagem_de_espera(segundos).endswith(texto)


# ---------------------------------------------------------------- quem é o cliente

def _pedido(host, ip_repassado=None):
    cabecalhos = [(b"x-cliente-ip", ip_repassado.encode())] if ip_repassado else []
    return Request({"type": "http", "client": (host, 1234), "headers": cabecalhos})


def test_ip_repassado_so_vale_vindo_do_proprio_servidor(monkeypatch):
    monkeypatch.delenv("API_PROXIES_CONFIAVEIS", raising=False)
    assert limites.ip_do_cliente(_pedido("127.0.0.1", "203.0.113.7")) == "203.0.113.7"
    assert limites.ip_do_cliente(_pedido("::1", "203.0.113.7")) == "203.0.113.7"
    # alguém de fora inventando o cabeçalho para escapar do limite: vale o IP da conexão
    assert limites.ip_do_cliente(_pedido("198.51.100.9", "203.0.113.7")) == "198.51.100.9"
    assert limites.ip_do_cliente(_pedido("127.0.0.1")) == "127.0.0.1"


def test_proxies_confiaveis_vem_do_ambiente(monkeypatch):
    monkeypatch.setenv("API_PROXIES_CONFIAVEIS", "10.0.0.5")
    assert limites.ip_do_cliente(_pedido("10.0.0.5", "203.0.113.7")) == "203.0.113.7"
    assert limites.ip_do_cliente(_pedido("127.0.0.1", "203.0.113.7")) == "127.0.0.1"


# ---------------------------------------------------------------- login

def test_conta_trava_depois_de_5_senhas_erradas_ate_com_a_senha_certa(client_anonimo, usuario_teste):
    for _ in range(5):
        assert login(client_anonimo, senha="errada-errada").status_code == 401
    travado = login(client_anonimo)  # senha CERTA: continua travado (o robô não sabe que acertou)
    assert travado.status_code == 429
    assert "Muitas tentativas" in travado.json()["detail"]
    assert 0 < int(travado.headers["retry-after"]) <= 15 * 60


def test_trava_vale_para_email_inexistente_e_nao_revela_quem_existe(client_anonimo, usuario_teste):
    for _ in range(5):
        login(client_anonimo, email="ninguem@exemplo.com", senha="errada-errada")
        login(client_anonimo, senha="errada-errada")
    limites.login_por_ip.zerar()
    inexistente = login(client_anonimo, email="ninguem@exemplo.com")
    existente = login(client_anonimo, senha="errada-errada")
    assert inexistente.status_code == existente.status_code == 429


def test_acertar_a_senha_zera_as_falhas_da_conta(client_anonimo, usuario_teste):
    for _ in range(4):
        login(client_anonimo, senha="errada-errada")
    assert login(client_anonimo).status_code == 200
    for _ in range(4):
        assert login(client_anonimo, senha="errada-errada").status_code == 401  # recomeçou do zero


def test_trava_de_uma_conta_nao_afeta_outra(client_anonimo, usuario_teste, sessao):
    from app.servicos.usuarios import criar_usuario
    criar_usuario(sessao, "Outra Pessoa", "outra@exemplo.com", "admin", "senha-da-outra-123")
    sessao.commit()
    for _ in range(5):
        login(client_anonimo, senha="errada-errada")
    assert login(client_anonimo, email="OUTRA@exemplo.com", senha="senha-da-outra-123").status_code == 200


def test_ip_tem_no_maximo_10_tentativas_de_login_por_minuto(client_anonimo, usuario_teste):
    for i in range(10):
        assert login(client_anonimo, email=f"pessoa{i}@exemplo.com", senha="x").status_code == 401
    assert login(client_anonimo).status_code == 429


def test_falha_de_login_vai_para_o_log_sem_o_email_inteiro(client_anonimo, usuario_teste, caplog):
    with caplog.at_level("WARNING", logger="concept.acesso"):
        login(client_anonimo, senha="errada-errada")
    assert "t***@exemplo.com" in caplog.text
    assert "teste@exemplo.com" not in caplog.text and "errada-errada" not in caplog.text


# ---------------------------------------------------------------- troca de senha

def test_troca_de_senha_trava_depois_de_5_senhas_atuais_erradas(client):
    def trocar(atual):
        return client.post("/auth/senha", json={"senha_atual": atual, "nova_senha": "uma-senha-nova-123"})
    for _ in range(5):
        assert trocar("errada-errada").status_code == 422
    assert trocar(SENHA_TESTE).status_code == 429


# ---------------------------------------------------------------- limite geral e corpo

def test_limite_geral_por_ip_devolve_429(client, monkeypatch):
    monkeypatch.setattr(limites, "geral", limites.Janela(3, 60))
    assert [client.get("/auth/eu").status_code for _ in range(4)] == [200, 200, 200, 429]
    resposta = client.get("/auth/eu")
    assert resposta.headers["retry-after"] and "Muitas tentativas" in resposta.json()["detail"]


def test_corpo_grande_demais_da_413_sem_chegar_na_rota(client):
    gigante = "x" * (1024 * 1024 + 1)
    resposta = client.post("/clientes", content=gigante, headers={"Content-Type": "application/json"})
    assert resposta.status_code == 413


def test_consulta_cortada_pelo_tempo_maximo_vira_503_com_mensagem(client):
    from app.main import banco_indisponivel
    erro = OperationalError("SELECT 1", {}, QueryCanceled("canceling statement due to statement timeout"))
    resposta = banco_indisponivel(None, erro)
    assert resposta.status_code == 503 and b"demorou demais" in resposta.body


def test_o_banco_corta_consulta_que_passa_do_tempo_maximo(engine, monkeypatch):
    monkeypatch.setenv("DB_TEMPO_MAXIMO_CONSULTA_MS", "200")
    from sqlalchemy import text
    from app import db
    rapido = db.criar_engine(engine.url.render_as_string(hide_password=False))
    try:
        with rapido.connect() as conn, pytest.raises(OperationalError) as erro:
            conn.execute(text("SELECT pg_sleep(1)"))
        assert isinstance(erro.value.orig, QueryCanceled)
    finally:
        rapido.dispose()


def test_docs_podem_ser_desligados(monkeypatch):
    from app import main
    monkeypatch.setenv("API_DOCS", "false")
    assert main._docs_ligados() is False
    monkeypatch.setenv("API_DOCS", "true")
    assert main._docs_ligados() is True
