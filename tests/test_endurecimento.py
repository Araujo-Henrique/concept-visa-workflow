"""Ajustes da auditoria de segurança: limites de tamanho, erro de dados sem vazar valores, corpo "chunked", segredo
fraco, trava do último administrador, impressão da idempotência com chave, log de uma linha só, docs desligados.

Cada teste prova um ajuste e (nos de concorrência e de corpo) falha se o ajuste for desfeito.
"""
import hashlib
import io
import logging
import re
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import DataError

from app import db, logs, seguranca
from app.main import app, valor_invalido_para_o_campo
from app.models import ChaveIdempotencia, Perfil, Usuario
from app.schemas.comum import MAX_PESSOAS_POR_PROCESSO
from app.servicos import usuarios as servico
from app.servicos.usuarios import criar_usuario
from app.servicos.workflow import ErroDeRegra
from tests.test_api import novo_cliente, novo_obt
from tests.test_autorizacao import como  # noqa: F401  (fixture)


# ---------------------------------------------------------------- limites de tamanho (colunas do banco)

def test_cliente_com_campos_do_tamanho_da_coluna_passa_e_um_caractere_a_mais_nao(client):
    ok = client.post("/clientes", json={"nome": "a" * 200, "email": "e" * 200, "grupo": "g" * 100})
    assert ok.status_code == 201
    for campo, tamanho in (("nome", 201), ("email", 201), ("grupo", 101)):
        corpo = {"nome": "Ana Souza", campo: "x" * tamanho}
        resposta = client.post("/clientes", json=corpo)
        assert resposta.status_code == 422, campo  # antes: passava e o banco recusava (erro 500)


def test_telefone_com_digitos_demais_e_recusado_e_o_normal_continua_funcionando(client):
    assert client.post("/clientes", json={"nome": "Ana Souza", "telefone": "+55 (41) 99999-8888"}).status_code == 201
    assert client.post("/clientes", json={"nome": "Bia", "telefone": "1" * 21}).status_code == 422
    assert client.post("/clientes", json={"nome": "Carla", "telefone": "1" * 41}).status_code == 422  # cru, longo demais
    assert client.post("/clientes", json={"nome": "Dora", "telefone": "1" * 20}).status_code == 201


def test_login_nao_aceita_email_nem_senha_gigantes(client_anonimo):
    longo_email = client_anonimo.post("/auth/login", json={"email": "a" * 201 + "@exemplo.com", "senha": "x"})
    longa_senha = client_anonimo.post("/auth/login", json={"email": "a@exemplo.com", "senha": "x" * 257})
    assert longo_email.status_code == longa_senha.status_code == 422  # nem chega a guardar a chave do bloqueio


def test_nome_de_usuario_respeita_a_coluna_de_120(client):
    ok = client.post("/usuarios", json={"nome": "n" * 120, "email": "a@exemplo.com", "perfil": "leitor"})
    assert ok.status_code == 201
    assert client.post("/usuarios", json={"nome": "n" * 121, "email": "b@exemplo.com", "perfil": "leitor"}).status_code == 422


def test_campos_de_processo_e_de_situacao_com_coluna_fixa_tem_teto(client, sessao, cliente):
    assert client.post("/processos-obt", json={"cliente_id": cliente.id, "situacao": "Processando",
                                               "codigo_rastreio": "r" * 61}).status_code == 422
    processo = novo_obt(client, cliente.id)
    resposta = client.post(f"/processos/{processo['id']}/situacao", json={"situacao": "s" * 41})
    assert resposta.status_code == 422


def test_texto_livre_continua_aceitando_notas_longas(client, cliente):
    # observacao/motivo são colunas Text: o teto é só o de corpo da requisição, e dado antigo nunca falha na leitura
    nota = "nota " * 1200  # ~6.000 caracteres
    processo = novo_obt(client, cliente.id, observacao=nota)
    assert client.get(f"/processos-obt/{processo['id']}").json()["observacao"] == nota.strip()


def test_um_processo_nao_cria_pessoas_sem_fim(client, cliente):
    extras = [f"Pessoa {i}" for i in range(MAX_PESSOAS_POR_PROCESSO)]  # + titular = 51
    recusado = client.post("/processos-obt", json={"cliente_id": cliente.id, "situacao": "Processando",
                                                   "solicitantes_extras": extras})
    assert recusado.status_code == 422
    aceito = client.post("/processos-obt", json={"cliente_id": cliente.id, "situacao": "Processando",
                                                 "solicitantes_extras": extras[:-1]})
    assert aceito.status_code == 201 and len(aceito.json()["solicitantes"]) == MAX_PESSOAS_POR_PROCESSO


def test_adicionar_pessoa_tambem_respeita_o_teto_do_processo(client, cliente):
    extras = [f"Pessoa {i}" for i in range(MAX_PESSOAS_POR_PROCESSO - 1)]
    processo = client.post("/processos-obt", json={"cliente_id": cliente.id, "situacao": "Processando",
                                                   "solicitantes_extras": extras}).json()
    resposta = client.post(f"/processos/{processo['id']}/solicitantes", json={"nome": "Uma a mais"})
    assert resposta.status_code == 409 and str(MAX_PESSOAS_POR_PROCESSO) in resposta.json()["detail"]


# ---------------------------------------------------------------- erro de dados: 422 e sem valores no log

def _erro_de_dados():
    return DataError("INSERT INTO clientes (nome) VALUES (%(nome)s)", {"nome": "NOME-SIGILOSO-DO-CLIENTE"},
                     Exception("value too long for type character varying(200)"))


def test_erro_de_dados_vira_422_sem_repetir_o_valor(caplog):
    with caplog.at_level(logging.INFO, logger="concept"):
        class Requisicao:
            method, url = "POST", type("U", (), {"path": "/clientes"})()
        resposta = valor_invalido_para_o_campo(Requisicao(), _erro_de_dados())
    assert resposta.status_code == 422
    assert "NOME-SIGILOSO" not in resposta.body.decode()
    assert "NOME-SIGILOSO" not in caplog.text


def test_erro_de_dados_de_ponta_a_ponta_nao_chega_ao_log_como_500(client, caplog):
    from app import deps

    def quebrada():
        raise _erro_de_dados()
        yield  # pragma: no cover

    app.dependency_overrides[deps.get_sessao] = quebrada
    try:
        with caplog.at_level(logging.INFO, logger="concept"):
            resposta = client.get("/clientes")
    finally:
        app.dependency_overrides.pop(deps.get_sessao)
    assert resposta.status_code == 422
    assert "NOME-SIGILOSO" not in resposta.text + caplog.text
    assert not any(r.exc_info for r in caplog.records)  # nenhum traceback no log


def test_o_engine_nunca_imprime_os_valores_enviados_ao_banco():
    engine = db.criar_engine("postgresql+psycopg://u:p@localhost/qualquer_test")
    assert engine.hide_parameters is True
    engine.dispose()


# ---------------------------------------------------------------- segredo de assinatura

SEGREDO_BOM = "9f2c7a41d8e05b36c1a47f90e2d83b5a6c04f17e92ab3d58"


def test_segredo_de_exemplo_curto_ou_repetitivo_e_recusado():
    assert seguranca.validar_segredo(SEGREDO_BOM) == SEGREDO_BOM
    com_tamanho_de_sobra = "troque-por-um-valor-longo-e-aleatorio"  # o do .env.example: tem mais de 32 e passava
    assert len(com_tamanho_de_sobra) >= seguranca.SEGREDO_MINIMO
    for ruim, trecho in ((com_tamanho_de_sobra, "exemplo"), ("ChangeMe" + "x" * 30, "exemplo"),
                         ("a" * 40, "repetitivo"), ("ab" * 20, "repetitivo"), ("curto", "pelo menos")):
        with pytest.raises(RuntimeError, match=trecho):
            seguranca.validar_segredo(ruim)


def test_token_nao_e_emitido_nem_lido_com_segredo_de_exemplo(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "troque-por-um-valor-longo-e-aleatorio")
    with pytest.raises(RuntimeError, match="exemplo"):
        seguranca.criar_token(1)
    with pytest.raises(RuntimeError, match="exemplo"):
        seguranca.ler_token("qualquer.coisa.aqui")  # a leitura também recusa o segredo fraco


def test_a_api_nem_sobe_com_segredo_de_exemplo(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "troque-por-um-valor-longo-e-aleatorio")
    with pytest.raises(RuntimeError, match="exemplo"):
        with TestClient(app):
            pass  # o lifespan roda ao entrar e recusa antes de atender qualquer pedido


def test_a_api_sobe_com_segredo_bom(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SEGREDO_BOM)
    with TestClient(app) as c:
        assert c.get("/saude").status_code == 200


def test_o_env_example_nao_traz_um_segredo_que_passe_na_validacao():
    exemplo = Path(__file__).resolve().parents[1] / ".env.example"
    linha = next(l for l in exemplo.read_text(encoding="utf-8").splitlines() if l.startswith("JWT_SECRET="))
    valor = linha.split("=", 1)[1].split("#")[0].strip()
    if valor:  # vazio é o ideal (a API não sobe até alguém definir); preenchido, não pode ser aceito
        with pytest.raises(RuntimeError):
            seguranca.validar_segredo(valor)


# ---------------------------------------------------------------- impressão da idempotência (HMAC)

def _corpo_enviado(client, caminho, json):
    return client.build_request("POST", caminho, json=json).content


def test_impressao_nao_e_um_sha256_puro_e_depende_do_segredo_do_servidor(monkeypatch):
    corpo = b'{"nome":"Ana","senha":"senha-do-admin-123"}'
    atual = seguranca.impressao_do_corpo(corpo)
    assert atual == seguranca.impressao_do_corpo(corpo)  # estável: a mesma chave+corpo continua casando
    assert atual != hashlib.sha256(corpo).hexdigest()  # não dá para testar senhas só com sha256 do corpo
    monkeypatch.setenv("JWT_SECRET", SEGREDO_BOM)
    assert seguranca.impressao_do_corpo(corpo) != atual  # com outro segredo, outra impressão


def test_a_tabela_guarda_a_impressao_com_chave_de_um_cadastro_com_senha(client, sessao):
    corpo = {"nome": "Alvo", "email": "alvo@exemplo.com", "perfil": "admin", "senha": "senha-do-novo-admin-123"}
    resposta = client.post("/usuarios", json=corpo, headers={"Idempotency-Key": "chave-de-teste-0001"})
    assert resposta.status_code == 201
    sessao.expire_all()
    linha = sessao.scalars(select(ChaveIdempotencia)).one()
    bytes_enviados = _corpo_enviado(client, "/usuarios", corpo)
    assert linha.impressao == seguranca.impressao_do_corpo(bytes_enviados)
    assert linha.impressao != hashlib.sha256(bytes_enviados).hexdigest()


# ---------------------------------------------------------------- corpo "chunked": o teto vale pelos bytes recebidos

def _em_pedacos(total_bytes: int, pedaco: int = 64 * 1024):
    enviados = 0
    while enviados < total_bytes:
        yield b" " * min(pedaco, total_bytes - enviados)
        enviados += pedaco


def test_corpo_chunked_acima_do_teto_toma_413_antes_de_ser_lido_por_inteiro(client_anonimo):
    # sem Content-Length (chunked): antes o teto só olhava o cabeçalho e o corpo era lido todo
    resposta = client_anonimo.post("/auth/login", content=_em_pedacos(3 * 1024 * 1024),
                                   headers={"Content-Type": "application/json"})
    assert resposta.status_code == 413 and resposta.json() == {"detail": "Dados grandes demais"}
    assert resposta.headers["X-Request-ID"]  # passou pelo log como qualquer erro


def test_corpo_chunked_pequeno_continua_funcionando(client_anonimo):
    def pedacos():
        yield b'{"email": "a@exemplo.com",'
        yield b' "senha": "qualquer-senha"}'
    resposta = client_anonimo.post("/auth/login", content=pedacos(), headers={"Content-Type": "application/json"})
    assert resposta.status_code == 401  # credencial errada, mas o corpo foi lido normalmente


def test_corpo_chunked_grande_tambem_para_na_rota_com_idempotencia(client):
    resposta = client.post("/clientes", content=_em_pedacos(2 * 1024 * 1024),
                           headers={"Content-Type": "application/json", "Idempotency-Key": "chave-de-teste-0001"})
    assert resposta.status_code == 413


def test_o_teto_por_content_length_continua_valendo(client_anonimo):
    resposta = client_anonimo.post("/auth/login", content=b"x" * (1024 * 1024 + 1))
    assert resposta.status_code == 413


# ---------------------------------------------------------------- log de uma linha só

def test_formato_texto_neutraliza_quebra_de_linha_e_controle():
    registro = logging.LogRecord("concept.api", logging.INFO, __file__, 1, "msg com\nquebra", (), None)
    registro.campos = {"caminho": "/x\nFAKE linha=1\r\x1b[31m", "status": 200}
    linha = logs._Formato(como_json=False).format(registro)
    assert "\n" not in linha and "\r" not in linha and "\x1b" not in linha
    assert "\\x0a" in linha and "\\x0d" in linha and "\\x1b" in linha
    assert "status=200" in linha  # o resto do registro segue igual


def test_caminho_com_quebra_de_linha_nao_forja_linha_no_log_de_ponta_a_ponta(client_anonimo):
    saida = io.StringIO()
    manipulador = logging.StreamHandler(saida)
    manipulador.setFormatter(logs._Formato(como_json=False))
    logger = logging.getLogger(logs.NOME_DO_LOGGER)
    logger.addHandler(manipulador)
    try:
        # %0D%0A o cliente de teste engole; %1B (ESC) e %0B (tab vertical) chegam ao log e provam o mesmo caminho
        client_anonimo.get("/zz%0BFAKE%20requisicao%20status=200%20usuario=1%1B[31m")
    finally:
        logger.removeHandler(manipulador)
    linhas = saida.getvalue().splitlines()
    assert len(linhas) == 1  # uma requisição, uma linha
    assert "FAKE" in linhas[0] and "\\x0b" in linhas[0] and "\\x1b" in linhas[0]  # o texto aparece, mas dentro da linha verdadeira


# ---------------------------------------------------------------- docs desligados por padrão

def test_docs_ficam_desligados_a_menos_que_se_peca(monkeypatch):
    from app import main
    monkeypatch.delenv("API_DOCS", raising=False)
    assert main._docs_ligados() is False
    for ligado in ("true", "1", "sim", "TRUE"):
        monkeypatch.setenv("API_DOCS", ligado)
        assert main._docs_ligados() is True
    for desligado in ("false", "0", "", "talvez"):
        monkeypatch.setenv("API_DOCS", desligado)
        assert main._docs_ligados() is False


# ---------------------------------------------------------------- último administrador: trava contra a corrida

def _dois_admins(sessao):
    a = criar_usuario(sessao, "Admin A", "a@exemplo.com", "admin", "senha-do-admin-a-123")
    b = criar_usuario(sessao, "Admin B", "b@exemplo.com", "admin", "senha-do-admin-b-123")
    sessao.commit()
    return a.id, b.id


def test_dois_admins_que_se_desativam_ao_mesmo_tempo_nao_deixam_zero(sessao):
    id_a, id_b = _dois_admins(sessao)
    primeiro_passou, liberar = threading.Event(), threading.Event()
    resultado = {}

    def a_desativa_b():
        with db.Session() as s:
            servico.atualizar_usuario(s, s.get(Usuario, id_b), s.get(Usuario, id_a), ativo=False)
            primeiro_passou.set()
            liberar.wait(5)  # segura a transação aberta: o segundo pedido chega no meio
            s.commit()
            resultado["a"] = "ok"

    def b_desativa_a():
        primeiro_passou.wait(5)
        with db.Session() as s:
            try:
                servico.atualizar_usuario(s, s.get(Usuario, id_a), s.get(Usuario, id_b), ativo=False)
                s.commit()
                resultado["b"] = "ok"
            except ErroDeRegra as erro:
                resultado["b"] = erro.status

    fios = [threading.Thread(target=a_desativa_b), threading.Thread(target=b_desativa_a)]
    for f in fios:
        f.start()
    primeiro_passou.wait(5)
    time.sleep(0.7)  # dá tempo de o segundo chegar à trava (sem trava, ele já teria passado e gravado)
    liberar.set()
    for f in fios:
        f.join(10)

    sessao.expire_all()
    ativos = sessao.scalar(select(func.count()).select_from(Usuario).join(Perfil)
                           .where(Perfil.nome == "admin", Usuario.ativo.is_(True)))
    assert resultado == {"a": "ok", "b": 409}  # o segundo esperou e viu que o outro já tinha saído
    assert ativos == 1


def test_dois_admins_que_se_rebaixam_ao_mesmo_tempo_tambem_nao_deixam_zero(sessao):
    id_a, id_b = _dois_admins(sessao)
    primeiro_passou, liberar = threading.Event(), threading.Event()
    resultado = {}

    def a_rebaixa_b():
        with db.Session() as s:
            servico.atualizar_usuario(s, s.get(Usuario, id_b), s.get(Usuario, id_a), perfil="atendente")
            primeiro_passou.set()
            liberar.wait(5)
            s.commit()

    def b_rebaixa_a():
        primeiro_passou.wait(5)
        with db.Session() as s:
            try:
                servico.atualizar_usuario(s, s.get(Usuario, id_a), s.get(Usuario, id_b), perfil="atendente")
                s.commit()
                resultado["b"] = "ok"
            except ErroDeRegra as erro:
                resultado["b"] = erro.status

    fios = [threading.Thread(target=a_rebaixa_b), threading.Thread(target=b_rebaixa_a)]
    for f in fios:
        f.start()
    primeiro_passou.wait(5)
    time.sleep(0.7)
    liberar.set()
    for f in fios:
        f.join(10)
    sessao.expire_all()
    admins = sessao.scalar(select(func.count()).select_from(Usuario).join(Perfil).where(Perfil.nome == "admin"))
    assert resultado["b"] == 409 and admins == 1


def test_mexer_em_quem_nao_e_admin_nao_trava_nada(sessao):
    _dois_admins(sessao)
    leitor = criar_usuario(sessao, "Leitor", "l@exemplo.com", "leitor")
    sessao.commit()
    admin = sessao.scalars(select(Usuario).where(Usuario.email == "a@exemplo.com")).one()
    servico.atualizar_usuario(sessao, leitor, admin, nome="Leitor Novo")
    sessao.commit()
    assert sessao.get(Usuario, leitor.id).nome == "Leitor Novo"


# ---------------------------------------------------------------- senha: admin não contorna a troca da própria senha

def test_admin_nao_redefine_a_propria_senha_pela_rota_de_administracao(client, usuario_teste):
    resposta = client.post(f"/usuarios/{usuario_teste.id}/senha", json={"senha": "uma-senha-nova-bem-longa-9"})
    assert resposta.status_code == 409 and "própria senha" in resposta.json()["detail"]


def test_admin_continua_redefinindo_a_senha_de_outro_admin(client, sessao):
    outro = criar_usuario(sessao, "Outro Admin", "outro@exemplo.com", "admin", "senha-do-outro-123")
    sessao.commit()
    assert client.post(f"/usuarios/{outro.id}/senha", json={"senha": "uma-senha-nova-bem-longa-9"}).status_code == 204


def test_script_nao_define_senha_para_quem_nao_e_admin(sessao):
    criar_usuario(sessao, "Atendente", "at@exemplo.com", "atendente")
    sessao.commit()
    with pytest.raises(ErroDeRegra, match="Só administradores têm senha"):
        servico.definir_senha(sessao, "at@exemplo.com", "uma-senha-bem-longa-123")


# ---------------------------------------------------------------- revogação de tokens (token_version)

def _logar(client_anonimo, email, senha):
    r = client_anonimo.post("/auth/login", json={"email": email, "senha": senha})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_token_antigo_sem_versao_continua_valendo_como_versao_zero(client, usuario_teste):
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone
    corpo = {"sub": str(usuario_teste.id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    antigo = pyjwt.encode(corpo, __import__("os").environ["JWT_SECRET"], algorithm="HS256")
    assert client.get("/auth/eu", headers={"Authorization": f"Bearer {antigo}"}).status_code == 200


def test_redefinir_a_senha_derruba_as_sessoes_antigas_da_pessoa(client, client_anonimo, sessao):
    alvo = criar_usuario(sessao, "Alvo", "alvo@exemplo.com", "admin", "senha-do-alvo-1234")
    sessao.commit()
    antigo = _logar(client_anonimo, "alvo@exemplo.com", "senha-do-alvo-1234")
    assert client_anonimo.get("/auth/eu", headers=antigo).status_code == 200
    assert client.post(f"/usuarios/{alvo.id}/senha", json={"senha": "outra-senha-bem-longa-9"}).status_code == 204
    assert client_anonimo.get("/auth/eu", headers=antigo).status_code == 401  # o token roubado morreu
    novo = _logar(client_anonimo, "alvo@exemplo.com", "outra-senha-bem-longa-9")
    assert client_anonimo.get("/auth/eu", headers=novo).status_code == 200


def test_trocar_a_propria_senha_derruba_as_outras_sessoes_mas_devolve_token_novo(client_anonimo, sessao):
    criar_usuario(sessao, "Dono", "dono@exemplo.com", "admin", "senha-do-dono-1234")
    sessao.commit()
    outra_sessao = _logar(client_anonimo, "dono@exemplo.com", "senha-do-dono-1234")
    esta = _logar(client_anonimo, "dono@exemplo.com", "senha-do-dono-1234")
    r = client_anonimo.post("/auth/senha", headers=esta,
                            json={"senha_atual": "senha-do-dono-1234", "nova_senha": "senha-nova-do-dono-99"})
    assert r.status_code == 200
    assert client_anonimo.get("/auth/eu", headers=esta).status_code == 401
    assert client_anonimo.get("/auth/eu", headers=outra_sessao).status_code == 401
    continua = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client_anonimo.get("/auth/eu", headers=continua).status_code == 200
    renovado = client_anonimo.post("/auth/renovar", headers=continua)  # a renovação mantém a versão
    assert renovado.status_code == 200
    assert client_anonimo.get("/auth/eu", headers={"Authorization": f"Bearer {renovado.json()['access_token']}"}).status_code == 200


def test_desativar_e_reativar_nao_ressuscita_o_token_de_antes(client, como, sessao):
    atendente = como("atendente")
    assert atendente.get("/auth/eu").status_code == 200
    client.patch(f"/usuarios/{atendente.usuario.id}", json={"ativo": False})
    client.patch(f"/usuarios/{atendente.usuario.id}", json={"ativo": True})
    assert atendente.get("/auth/eu").status_code == 401


def test_admin_rebaixado_perde_a_senha_e_o_token(client, client_anonimo, sessao):
    alvo = criar_usuario(sessao, "Outro", "outro@exemplo.com", "admin", "senha-do-outro-1234")
    sessao.commit()
    token = _logar(client_anonimo, "outro@exemplo.com", "senha-do-outro-1234")
    client.patch(f"/usuarios/{alvo.id}", json={"perfil": "atendente"})
    assert client_anonimo.get("/auth/eu", headers=token).status_code == 401


# ---------------------------------------------------------------- seed e conexão

def test_seed_recusa_banco_com_usuario_que_nao_e_do_seed(sessao):
    from app.seed import semear
    criar_usuario(sessao, "Gente de Verdade", "gente@empresa.com.br", "admin", "senha-bem-longa-123")
    sessao.commit()
    with pytest.raises(RuntimeError, match="não são do seed"):
        semear(sessao, None, quantidade=2)
    semear(sessao, None, quantidade=2, aceitar_usuarios_existentes=True)  # o admin de desenvolvimento, de propósito


def test_a_conexao_com_o_banco_tem_prazo_para_abrir(monkeypatch):
    capturado = {}
    monkeypatch.setattr(db, "create_engine", lambda url, **kw: capturado.update(kw))
    db.criar_engine("postgresql+psycopg://u:p@localhost/qualquer_test")
    assert capturado["connect_args"]["connect_timeout"] == 5
