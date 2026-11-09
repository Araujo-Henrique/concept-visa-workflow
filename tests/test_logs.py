"""Logs: um registro por requisição, com um código (id) que a pessoa pode informar ao suporte.

O mais importante aqui é o que NÃO pode aparecer no log: senha, token e parâmetros da URL.
"""
import logging
import re

import pytest

from app import deps, logs
from app.main import app


def _linhas_de_requisicao(caplog):
    return [r for r in caplog.records if r.name == "concept.api" and r.getMessage() == "requisicao"]


@pytest.fixture
def capturar(caplog):
    with caplog.at_level(logging.INFO, logger="concept"):
        yield caplog


def test_toda_resposta_traz_um_id_de_requisicao(client_anonimo):
    resposta = client_anonimo.post("/auth/login", json={"email": "a@b.com", "senha": "x"})
    assert re.fullmatch(r"[0-9a-f]{12}", resposta.headers["X-Request-ID"])


def test_cada_requisicao_tem_o_seu_id(client_anonimo):
    ids = {client_anonimo.get("/auth/eu").headers["X-Request-ID"] for _ in range(3)}
    assert len(ids) == 3


def test_id_enviado_de_fora_e_mantido_se_for_simples(client_anonimo):
    resposta = client_anonimo.get("/auth/eu", headers={"X-Request-ID": "abc-123_x.y"})
    assert resposta.headers["X-Request-ID"] == "abc-123_x.y"


@pytest.mark.parametrize("sujo", ["com espaco", "a" * 65, "x\nlinha-falsa", "<script>"])
def test_id_enviado_de_fora_com_lixo_e_trocado(client_anonimo, sujo):
    # sem isso alguém forjaria linhas no log através do cabeçalho
    resposta = client_anonimo.get("/auth/eu", headers={"X-Request-ID": sujo.replace("\n", " ")})
    assert resposta.headers["X-Request-ID"] != sujo
    assert re.fullmatch(r"[0-9a-f]{12}", resposta.headers["X-Request-ID"])


def test_linha_da_requisicao_diz_quem_o_que_e_como_terminou(client, usuario_teste, capturar):
    resposta = client.get("/clientes")
    [linha] = _linhas_de_requisicao(capturar)
    campos = linha.campos
    assert (campos["metodo"], campos["caminho"], campos["status"]) == ("GET", "/clientes", 200)
    assert campos["usuario"] == usuario_teste.id
    assert campos["ms"] >= 0 and campos["ip"]
    assert resposta.headers["X-Request-ID"]


def test_parametros_da_url_nao_vao_para_o_log(client, capturar):
    client.get("/clientes", params={"nome": "Maria Segredo", "telefone": "41988887777"})
    texto = " ".join(str(vars(r)) for r in capturar.records)
    assert "Segredo" not in texto and "41988887777" not in texto


def test_nivel_do_registro_acompanha_o_status(client, capturar):
    client.get("/clientes")  # 200
    client.get("/clientes/999999")  # 404
    niveis = {r.campos["status"]: r.levelno for r in _linhas_de_requisicao(capturar)}
    assert niveis == {200: logging.INFO, 404: logging.WARNING}


def test_login_nao_grava_senha_nem_token_e_usa_o_mesmo_id(client_anonimo, usuario_teste):
    import io
    saida = io.StringIO()
    manipulador = logging.StreamHandler(saida)
    manipulador.setFormatter(logs._Formato(como_json=False))
    logger = logging.getLogger(logs.NOME_DO_LOGGER)
    logger.addHandler(manipulador)
    try:
        senha = "senha-secreta-que-nao-pode-vazar"
        errada = client_anonimo.post("/auth/login", json={"email": "teste@exemplo.com", "senha": senha})
        certa = client_anonimo.post("/auth/login", json={"email": "teste@exemplo.com", "senha": "senha-de-teste-123"})
    finally:
        logger.removeHandler(manipulador)
    texto = saida.getvalue()
    assert senha not in texto and "senha-de-teste-123" not in texto
    assert certa.json()["access_token"] not in texto
    # o aviso "login falhou" e a linha da requisição saem sob o mesmo id que a resposta devolveu
    id_req = errada.headers["X-Request-ID"]
    linha_falha = next(l for l in texto.splitlines() if "login falhou" in l)
    linha_http = next(l for l in texto.splitlines() if "requisicao" in l and "status=401" in l)
    assert f"id={id_req}" in linha_falha and f"id={id_req}" in linha_http


def test_erro_nao_tratado_vira_500_com_codigo_e_traceback_no_log(client, capturar):
    def quebrada():
        raise RuntimeError("falha interna secreta")
        yield  # pragma: no cover

    app.dependency_overrides[deps.get_sessao] = quebrada
    try:
        resposta = client.get("/clientes")
    finally:
        app.dependency_overrides.pop(deps.get_sessao)
    assert resposta.status_code == 500
    corpo = resposta.json()
    assert corpo["id"] == resposta.headers["X-Request-ID"]
    assert "secreta" not in resposta.text  # a pessoa vê o código, nunca o detalhe técnico
    erro = next(r for r in capturar.records if r.levelno == logging.ERROR and r.exc_info)
    assert "falha interna secreta" in str(erro.exc_info[1])
    assert _linhas_de_requisicao(capturar)[-1].campos["status"] == 500


class TestFormato:
    def _registro(self, **campos):
        r = logging.LogRecord("concept.api", logging.WARNING, __file__, 1, "requisicao", (), None)
        r.campos = campos
        return r

    def test_texto(self):
        token = logs.id_da_requisicao.set("abc123")
        try:
            linha = logs._Formato(como_json=False).format(self._registro(metodo="GET", status=404))
        finally:
            logs.id_da_requisicao.reset(token)
        assert "WARNING" in linha and "id=abc123" in linha and "metodo=GET status=404" in linha

    def test_json_e_uma_linha_valida(self):
        import json
        linha = logs._Formato(como_json=True).format(self._registro(metodo="GET", status=404, nome="João"))
        dado = json.loads(linha)
        assert "\n" not in linha
        assert dado["nivel"] == "WARNING" and dado["status"] == 404 and dado["nome"] == "João"
        assert {"quando", "origem", "id", "mensagem"} <= dado.keys()


def test_configurar_varias_vezes_nao_duplica_a_saida(monkeypatch):
    logger = logging.getLogger(logs.NOME_DO_LOGGER)
    logs.configurar()
    logs.configurar()
    assert sum(1 for h in logger.handlers if getattr(h, "_do_concept", False)) == 1


def test_nivel_invalido_cai_no_padrao(monkeypatch):
    monkeypatch.setenv("LOG_NIVEL", "barulhento")
    logs.configurar()
    assert logging.getLogger(logs.NOME_DO_LOGGER).level == logging.INFO


def test_log_em_arquivo_com_rotacao_guarda_so_as_copias_pedidas(monkeypatch, tmp_path):
    arquivo = tmp_path / "pasta-nova" / "api.log"
    monkeypatch.setenv("LOG_ARQUIVO", str(arquivo))
    monkeypatch.setattr(logs, "_inteiro", lambda nome, padrao: {"LOG_ARQUIVO_MB": 1, "LOG_ARQUIVO_COPIAS": 2}[nome])
    logs.configurar()
    logger = logging.getLogger("concept.teste")
    try:
        # perto de 1 MB por arquivo: 5 MB de linhas forçam várias rotações
        for _ in range(5200):
            logger.warning("x" * 1000)
        for h in logging.getLogger(logs.NOME_DO_LOGGER).handlers:
            h.flush()
    finally:
        monkeypatch.setenv("LOG_ARQUIVO", "")
        logs.configurar()  # solta o arquivo (necessário no Windows para apagar a pasta)
    nomes = sorted(p.name for p in arquivo.parent.iterdir())
    assert nomes == ["api.log", "api.log.1", "api.log.2"]  # nunca passa de 2 cópias: a mais velha foi apagada
    assert "WARNING" in arquivo.read_text(encoding="utf-8")


def test_inteiro_invalido_ou_zero_usa_valor_seguro(monkeypatch):
    monkeypatch.setenv("LOG_ARQUIVO_MB", "abc")
    assert logs._inteiro("LOG_ARQUIVO_MB", 5) == 5
    monkeypatch.setenv("LOG_ARQUIVO_MB", "0")
    assert logs._inteiro("LOG_ARQUIVO_MB", 5) == 1
