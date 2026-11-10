import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import permissoes, seguranca
from app.main import app
from app.models import AuditoriaUsuario, Usuario
from app.servicos.usuarios import criar_usuario
from tests.conftest import SENHA_TESTE
from tests.test_api import novo_cliente, novo_obt


@pytest.fixture
def como(sessao):
    """como("leitor") devolve um cliente HTTP logado com um usuário novo desse perfil."""
    contador = {"n": 0}

    def fabrica(perfil: str, ativo: bool = True) -> TestClient:
        contador["n"] += 1
        usuario = criar_usuario(sessao, f"{perfil} {contador['n']}", f"{perfil}{contador['n']}@exemplo.com",
                                perfil, SENHA_TESTE)
        usuario.ativo = ativo
        sessao.commit()
        c = TestClient(app)
        c.headers["Authorization"] = f"Bearer {seguranca.criar_token(usuario.id)}"
        c.usuario = usuario
        return c

    return fabrica


# ---------------------------------------------------------------- permissões por perfil

def test_regra_de_permissao_por_metodo():
    assert [permissoes.exigida_pelo_metodo(m) for m in ("GET", "POST", "PATCH", "PUT", "DELETE")] == [
        "ler", "escrever", "escrever", "escrever", "apagar"]
    assert permissoes.pode("admin", "apagar") and not permissoes.pode("atendente", "apagar")
    assert not permissoes.pode("perfil-inventado", "ler")  # perfil desconhecido: nega por padrão


def test_leitor_so_consulta(como, client):
    leitor = como("leitor")
    ana = novo_cliente(client)  # criado por um admin
    assert leitor.get("/clientes").status_code == 200
    assert leitor.get("/painel").status_code == 200
    assert leitor.get(f"/clientes/{ana['id']}").status_code == 200
    assert leitor.post("/clientes", json={"nome": "Novo"}).status_code == 403
    assert leitor.patch(f"/clientes/{ana['id']}", json={"grupo": "x"}).status_code == 403
    assert leitor.delete(f"/clientes/{ana['id']}").status_code == 403
    assert leitor.post("/processos-obt", json={"cliente_id": ana["id"], "situacao": "Pago"}).status_code == 403


def test_atendente_cria_edita_e_exclui_cliente_mas_nao_apaga_o_resto(como, client):
    atendente = como("atendente")
    ana = atendente.post("/clientes", json={"nome": "Ana Souza"}).json()
    assert atendente.patch(f"/clientes/{ana['id']}", json={"grupo": "Familia"}).status_code == 200
    processo = atendente.post("/processos-obt", json={"cliente_id": ana["id"], "situacao": "Processando"}).json()
    assert atendente.post(f"/processos/{processo['id']}/situacao", json={"situacao": "Pago"}).status_code == 200
    assert atendente.post(f"/processos/{processo['id']}/solicitantes", json={"nome": "Filho"}).status_code == 201
    # processo, pessoa e DS-160 soltos seguem só do admin: só a exclusão de CLIENTE é restaurável pelo admin
    assert atendente.delete(f"/processos-obt/{processo['id']}").status_code == 403
    assert atendente.delete(f"/solicitantes/{processo['solicitantes'][0]['id']}").status_code == 403
    # cliente com processo: precisa confirmar com_processos; com ela, o atendente pode (o admin restaura depois)
    assert atendente.delete(f"/clientes/{ana['id']}").status_code == 409
    assert atendente.delete(f"/clientes/{ana['id']}", params={"com_processos": "true"}).status_code == 204


def test_admin_apaga(como):
    admin = como("admin")
    ana = admin.post("/clientes", json={"nome": "Ana Souza"}).json()
    assert admin.delete(f"/clientes/{ana['id']}").status_code == 204


def test_so_admin_administra_usuarios(como):
    for perfil in ("leitor", "atendente"):
        c = como(perfil)
        assert c.get("/usuarios").status_code == 403
        assert c.post("/usuarios", json={"nome": "X", "email": "x@exemplo.com", "perfil": "leitor"}).status_code == 403
    assert como("admin").get("/usuarios").status_code == 200


def test_401_sem_login_e_403_com_login_sem_permissao(como, client_anonimo):
    assert client_anonimo.get("/usuarios").status_code == 401  # quem é você?
    assert como("leitor").get("/usuarios").status_code == 403  # sei quem é, mas não pode


def test_perfil_alterado_vale_na_proxima_requisicao(como, client):
    atendente = como("atendente")
    assert atendente.post("/clientes", json={"nome": "Ana"}).status_code == 201
    client.patch(f"/usuarios/{atendente.usuario.id}", json={"perfil": "leitor"})  # o admin rebaixa
    assert atendente.post("/clientes", json={"nome": "Bia"}).status_code == 403  # mesmo token de antes


# ---------------------------------------------------------------- administração de usuários

def test_admin_cria_admin_com_senha_e_ele_consegue_entrar(client, client_anonimo):
    criado = client.post("/usuarios", json={"nome": "Nova Pessoa", "email": "nova@exemplo.com",
                                            "perfil": "admin", "senha": "senha-bem-longa-1"})
    assert criado.status_code == 201
    assert criado.json()["perfil"] == "admin" and "senha_hash" not in criado.json()
    login = client_anonimo.post("/auth/login", json={"email": "nova@exemplo.com", "senha": "senha-bem-longa-1"})
    assert login.status_code == 200


def test_so_admin_tem_senha_os_outros_perfis_sao_criados_sem_ela(client, client_anonimo):
    dados = {"nome": "Nova Pessoa", "email": "nova@exemplo.com", "perfil": "atendente"}
    recusado = client.post("/usuarios", json={**dados, "senha": "senha-bem-longa-1"})
    assert recusado.status_code == 422 and "Google" in recusado.json()["detail"]
    assert client.post("/usuarios", json=dados).status_code == 201  # sem senha: entra só com o Google
    entrada = client_anonimo.post("/auth/login", json={"email": "nova@exemplo.com", "senha": "qualquer-1234"})
    assert entrada.status_code == 401


def test_criar_usuario_valida_perfil_email_e_senha(client):
    base = {"nome": "X", "email": "x@exemplo.com", "perfil": "admin", "senha": "senha-bem-longa-1"}
    assert client.post("/usuarios", json={**base, "perfil": "chefe"}).status_code == 422
    assert client.post("/usuarios", json={**base, "senha": "curta"}).status_code == 422
    assert client.post("/usuarios", json=base).status_code == 201
    assert client.post("/usuarios", json={**base, "email": "X@EXEMPLO.com"}).status_code == 409


def test_desativar_pelo_admin_corta_o_acesso_na_hora(como, client):
    atendente = como("atendente")
    assert atendente.get("/clientes").status_code == 200
    resposta = client.patch(f"/usuarios/{atendente.usuario.id}", json={"ativo": False})
    assert resposta.status_code == 200 and resposta.json()["ativo"] is False
    assert atendente.get("/clientes").status_code == 403  # mesmo token, ainda dentro da validade


def test_nunca_fica_sem_administrador_ativo(client, usuario_teste, como):
    # usuario_teste é o único admin: não pode se desativar nem se rebaixar
    assert client.patch(f"/usuarios/{usuario_teste.id}", json={"ativo": False}).status_code == 409
    assert client.patch(f"/usuarios/{usuario_teste.id}", json={"perfil": "leitor"}).status_code == 409
    segundo = como("admin")
    # com outro admin ativo, a mudança é permitida
    assert client.patch(f"/usuarios/{segundo.usuario.id}", json={"ativo": False}).status_code == 200
    # ...mas o outro voltou a ser o único: continua protegido
    assert client.patch(f"/usuarios/{usuario_teste.id}", json={"ativo": False}).status_code == 409


def test_admin_pode_se_rebaixar_se_houver_outro_admin(client, usuario_teste, como):
    como("admin")
    assert client.patch(f"/usuarios/{usuario_teste.id}", json={"perfil": "atendente"}).status_code == 200


def test_patch_de_usuario_recusa_vazio_e_campos_extras(client, usuario_teste):
    url = f"/usuarios/{usuario_teste.id}"
    assert client.patch(url, json={"perfil": None}).status_code == 422
    assert client.patch(url, json={"email": "outro@exemplo.com"}).status_code == 422  # e-mail não muda
    assert client.patch("/usuarios/999", json={"ativo": True}).status_code == 404


def test_auditoria_registra_quem_mudou_o_que(como, client, usuario_teste, sessao):
    alvo = como("leitor")
    client.patch(f"/usuarios/{alvo.usuario.id}", json={"perfil": "atendente", "ativo": False, "nome": "Novo Nome"})
    linhas = client.get(f"/usuarios/{alvo.usuario.id}/auditoria").json()
    assert [(l["campo"], l["valor_anterior"], l["valor_novo"]) for l in linhas] == [
        ("perfil", "leitor", "atendente"),
        ("senha", None, "removida (deixou de ser administrador)"),  # o leitor do teste tinha senha: só admin tem
        ("ativo", "True", "False"), ("nome", f"leitor {alvo.usuario.id - usuario_teste.id}", "Novo Nome")]
    assert {l["feito_por_id"] for l in linhas} == {usuario_teste.id}
    assert all(l["criado_em"] for l in linhas)


def test_auditoria_da_senha_nunca_guarda_a_senha(como, client):
    alvo = como("admin")
    client.post(f"/usuarios/{alvo.usuario.id}/senha", json={"senha": "senha-redefinida-1"})
    linhas = client.get(f"/usuarios/{alvo.usuario.id}/auditoria").json()
    assert [(l["campo"], l["valor_anterior"], l["valor_novo"]) for l in linhas] == [("senha", None, "redefinida")]
    assert "senha-redefinida-1" not in str(linhas)


def test_quem_deixa_de_ser_admin_perde_a_senha_e_passa_a_entrar_so_com_o_google(como, client, client_anonimo, sessao):
    alvo = como("admin")
    email = alvo.usuario.email
    assert client_anonimo.post("/auth/login", json={"email": email, "senha": SENHA_TESTE}).status_code == 200
    client.patch(f"/usuarios/{alvo.usuario.id}", json={"perfil": "atendente"})
    sessao.expire_all()
    assert sessao.get(type(alvo.usuario), alvo.usuario.id).senha_hash is None
    assert client_anonimo.post("/auth/login", json={"email": email, "senha": SENHA_TESTE}).status_code == 401
    campos = [(l["campo"], l["valor_novo"]) for l in client.get(f"/usuarios/{alvo.usuario.id}/auditoria").json()]
    assert ("senha", "removida (deixou de ser administrador)") in campos
    # e não dá para redefinir senha de quem não é admin
    assert client.post(f"/usuarios/{alvo.usuario.id}/senha", json={"senha": "senha-redefinida-1"}).status_code == 409


def test_mudanca_sem_efeito_nao_gera_auditoria(client, como):
    alvo = como("leitor")
    client.patch(f"/usuarios/{alvo.usuario.id}", json={"perfil": "leitor", "ativo": True})
    assert client.get(f"/usuarios/{alvo.usuario.id}/auditoria").json() == []


def test_listar_usuarios_com_filtros(client, como):
    como("leitor"); como("atendente", ativo=False)
    assert len(client.get("/usuarios").json()) == 3  # o admin do teste + 2
    assert [u["perfil"] for u in client.get("/usuarios", params={"perfil": "atendente"}).json()] == ["atendente"]
    assert len(client.get("/usuarios", params={"ativo": False}).json()) == 1


# ---------------------------------------------------------------- senha

def test_admin_troca_a_propria_senha(como, client_anonimo):
    admin = como("admin")
    email = admin.usuario.email
    atual_errada = {"senha_atual": "errada-qualquer-1", "nova_senha": "nova-senha-longa-1"}
    assert admin.post("/auth/senha", json=atual_errada).status_code == 422
    assert admin.post("/auth/senha", json={"senha_atual": SENHA_TESTE, "nova_senha": "curta"}).status_code == 422
    ok = {"senha_atual": SENHA_TESTE, "nova_senha": "nova-senha-longa-1"}
    assert admin.post("/auth/senha", json=ok).status_code == 204
    assert client_anonimo.post("/auth/login", json={"email": email, "senha": SENHA_TESTE}).status_code == 401
    assert client_anonimo.post("/auth/login", json={"email": email, "senha": "nova-senha-longa-1"}).status_code == 200


@pytest.mark.parametrize("perfil", ["atendente", "leitor"])
def test_so_admin_usa_senha_os_outros_entram_com_o_google(como, client_anonimo, perfil):
    pessoa = como(perfil)
    resposta = pessoa.post("/auth/senha", json={"senha_atual": SENHA_TESTE, "nova_senha": "nova-senha-longa-1"})
    assert resposta.status_code == 403 and "Google" in resposta.json()["detail"]
    # mesmo com a senha CERTA no banco, quem não é admin não entra por senha (e a resposta é a de sempre)
    entrada = client_anonimo.post("/auth/login", json={"email": pessoa.usuario.email, "senha": SENHA_TESTE})
    assert entrada.status_code == 401 and entrada.json() == {"detail": "E-mail ou senha incorretos"}


def test_trocar_senha_exige_login(client_anonimo):
    assert client_anonimo.post("/auth/senha", json={"senha_atual": "x", "nova_senha": "y"}).status_code == 401


# ---------------------------------------------------------------- nenhuma rota fica de fora

# Rotas sem login por natureza: entrar (senha de admin ou Google) e saber a config pública do Google.
PUBLICAS = {("POST", "/auth/login"), ("POST", "/auth/google"), ("GET", "/auth/google/config"),
            ("GET", "/saude"), ("GET", "/pronto")}


def _rotas_da_api():
    """(método, caminho) de TODAS as rotas. Lê o OpenAPI porque `app.routes` agrupa as rotas incluídas num
    objeto sem `path` (um percorrer-e-pular silencioso deixaria o teste passando sem verificar nada)."""
    paginas = app.openapi()["paths"]
    return [(metodo.upper(), caminho) for caminho, metodos in paginas.items() for metodo in metodos
            if metodo.upper() in {"GET", "POST", "PATCH", "PUT", "DELETE"}]


def test_a_lista_de_rotas_nao_esta_vazia_e_inclui_as_conhecidas():
    rotas = _rotas_da_api()
    assert len(rotas) > 30
    assert {("POST", "/auth/login"), ("POST", "/auth/google"), ("GET", "/clientes"),
            ("POST", "/usuarios")} <= set(rotas)


def test_toda_rota_exceto_as_publicas_exige_autenticacao():
    """Percorre as rotas registradas: se alguém criar uma rota nova sem proteção, este teste falha."""
    client = TestClient(app)
    sem_protecao = []
    for metodo, caminho in _rotas_da_api():
        if (metodo, caminho) in PUBLICAS:
            continue
        url = re.sub(r"\{[^}]+\}", "1", caminho)  # troca os {parametros} por um valor qualquer
        resposta = client.request(metodo, url, json={})
        if resposta.status_code != 401:
            sem_protecao.append((metodo, caminho, resposta.status_code))
    assert sem_protecao == []


def test_leitor_nao_exclui_cliente_mas_atendente_e_admin_sim(como):
    admin = como("admin")
    cliente = novo_cliente(admin, "Pediu Para Sair")
    novo_obt(admin, cliente["id"])
    assert como("leitor").delete(f"/clientes/{cliente['id']}", params={"com_processos": "true"}).status_code == 403
    assert como("atendente").delete(f"/clientes/{cliente['id']}", params={"com_processos": "true"}).status_code == 204
    outro = novo_cliente(admin, "Outro Cliente")
    assert admin.delete(f"/clientes/{outro['id']}").status_code == 204


def test_permissao_de_excluir_cliente_nao_vaza_para_outras_rotas_de_delete():
    # a exceção vale só para o DELETE do cliente; qualquer outro DELETE continua exigindo `apagar`
    assert permissoes.exigida_pelo_metodo("DELETE", "/clientes/{cliente_id}") == "apagar_cliente"
    for rota in ("/processos-obt/{processo_id}", "/solicitantes/{solicitante_id}",
                 "/formularios-ds160/{formulario_id}", None):
        assert permissoes.exigida_pelo_metodo("DELETE", rota) == "apagar"
    assert permissoes.exigida_pelo_metodo("PATCH", "/clientes/{cliente_id}") == "escrever"  # só DELETE
    assert permissoes.pode("atendente", "apagar_cliente") and not permissoes.pode("atendente", "apagar")
    assert not permissoes.pode("leitor", "apagar_cliente")
