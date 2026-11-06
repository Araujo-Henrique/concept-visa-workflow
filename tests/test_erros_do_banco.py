"""A rede de segurança de main.py: o banco é a palavra final, e a API traduz o erro dele em resposta limpa.

As regras normalmente são checadas antes de gravar; estes handlers pegam o que escapa (por exemplo, duas
requisições simultâneas passando pela checagem ao mesmo tempo). Por isso o erro é provocado direto:
pelo caminho normal da API ele quase nunca chega aqui.
"""
import json

import pytest
from psycopg import errors as pg
from sqlalchemy.exc import IntegrityError, OperationalError

from app import deps
from app.main import app, banco_indisponivel, violacao_de_regra


def _integridade(orig: Exception) -> IntegrityError:
    return IntegrityError("INSERT INTO ...", {}, orig)


def _corpo(resposta) -> dict:
    return json.loads(resposta.body)


def test_os_tradutores_estao_registrados_no_app():
    # sem o registro, o erro do banco viraria um 500 com o texto do SQL
    assert app.exception_handlers[IntegrityError] is violacao_de_regra
    assert app.exception_handlers[OperationalError] is banco_indisponivel


@pytest.mark.parametrize("orig, status", [
    (pg.UniqueViolation(), 409),
    (pg.ForeignKeyViolation(), 409),
    (pg.CheckViolation(), 422),
    (pg.NotNullViolation(), 422),
])
def test_violacao_do_banco_vira_409_ou_422(orig, status):
    resposta = violacao_de_regra(None, _integridade(orig))
    assert resposta.status_code == status


def test_mensagens_de_duplicidade_e_de_vinculo_sao_diferentes():
    duplicado = _corpo(violacao_de_regra(None, _integridade(pg.UniqueViolation())))["detail"]
    vinculo = _corpo(violacao_de_regra(None, _integridade(pg.ForeignKeyViolation())))["detail"]
    assert "Já existe" in duplicado
    assert "vinculado" in vinculo
    assert duplicado != vinculo


def test_a_resposta_nao_vaza_sql_nem_detalhe_do_banco():
    erro = IntegrityError("INSERT INTO clientes (nome) VALUES ('segredo')", {"nome": "segredo"},
                          pg.UniqueViolation("duplicate key value violates unique constraint uq_x"))
    texto = violacao_de_regra(None, erro).body.decode()
    assert "INSERT" not in texto and "segredo" not in texto and "uq_x" not in texto


def test_banco_indisponivel_vira_503():
    resposta = banco_indisponivel(None, OperationalError("SELECT 1", {}, Exception("conexão recusada")))
    assert resposta.status_code == 503
    assert _corpo(resposta) == {"detail": "Banco de dados indisponível"}


def test_503_de_ponta_a_ponta_quando_a_conexao_cai(client):
    """Do pedido HTTP até a resposta: a sessão falha ao abrir e o usuário recebe 503, não 500."""
    def sessao_que_falha():
        raise OperationalError("SELECT 1", {}, Exception("conexão recusada"))
        yield  # pragma: no cover  (torna a função um gerador, como a dependência original)

    app.dependency_overrides[deps.get_sessao] = sessao_que_falha
    try:
        resposta = client.get("/clientes")
    finally:
        app.dependency_overrides.pop(deps.get_sessao, None)
    assert resposta.status_code == 503
    assert resposta.json() == {"detail": "Banco de dados indisponível"}
