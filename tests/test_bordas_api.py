"""Regras e filtros da API que a medição de cobertura mostrou sem nenhum teste.

Cada teste aqui fecha um buraco apontado pelo relatório de cobertura (ver README, seção de testes).
"""
import pytest

from app.servicos.workflow import ErroDeRegra, mudar_situacao
from tests.test_autorizacao import como  # noqa: F401  (fixture)
from tests.test_api import novo_cliente, novo_obt
from tests.test_workflow import muda, processo_obt


# ---------------------------------------------------------------- regra da renovação

def test_renovacao_com_data_de_casv_exige_consulado(client):
    """Mesma regra do OBT, mas na renovação (RENBase tem o próprio validador, que ninguém exercitava)."""
    cliente = novo_cliente(client)
    base = {"cliente_id": cliente["id"], "situacao": "Cadastro"}
    recusado = client.post("/processos-ren", json={**base, "data_casv": "2026-12-01"})
    assert recusado.status_code == 422
    # a mensagem é a da API ("informe o consulado"), não o erro genérico do CHECK do banco, que também daria 422
    assert "informe o consulado" in recusado.text
    criado = client.post("/processos-ren", json={**base, "data_casv": "2026-12-01", "consulado": "SP"})
    assert criado.status_code == 201
    # sem data, o consulado pode ficar vazio
    assert client.post("/processos-ren", json=base).status_code == 201


def test_patch_da_renovacao_revalida_com_o_que_ja_esta_gravado(client):
    cliente = novo_cliente(client)
    ren = client.post("/processos-ren", json={"cliente_id": cliente["id"], "situacao": "Cadastro"}).json()
    url = f"/processos-ren/{ren['id']}"
    recusado = client.patch(url, json={"data_casv": "2026-12-01"})
    assert recusado.status_code == 422 and "informe o consulado" in recusado.text
    assert client.patch(url, json={"data_casv": "2026-12-01", "consulado": "RIO"}).status_code == 200


# ---------------------------------------------------------------- reabrir processo concluído

def test_reabrir_sem_motivo_diz_o_que_falta(client):
    """O banco também recusa (CHECK reaberto_exige_motivo), mas só com um erro genérico. A mensagem clara
    vem da regra do serviço, e é ela que o usuário da tela vê."""
    processo = processo_obt(client)
    muda(client, processo["id"], "Concluido")
    recusado = muda(client, processo["id"], "Processando")
    assert recusado.status_code == 422
    assert "motivo" in recusado.json()["detail"].lower()
    assert "regra do banco" not in recusado.text


def test_servico_recusa_reabrir_sem_motivo_sem_depender_do_banco(client, sessao):
    """O serviço é reaproveitado pela importação e pelas integrações: a regra tem que valer nele, não só na rota."""
    processo = processo_obt(client)
    muda(client, processo["id"], "Concluido")
    sessao.expire_all()
    with pytest.raises(ErroDeRegra, match="motivo"):
        mudar_situacao(sessao, processo["id"], "Processando", motivo="   ")
    sessao.rollback()


# ---------------------------------------------------------------- filtros

def test_filtro_de_clientes_por_grupo_e_por_telefone(client):
    novo_cliente(client, "Ana Souza", grupo="Familia Souza", telefone="41999990001")
    novo_cliente(client, "Bia Souza", grupo="Familia Souza", telefone="41999990002")
    novo_cliente(client, "Caio Lima", grupo="Familia Lima", telefone="41999990003")

    def nomes(**params):
        return sorted(c["nome"] for c in client.get("/clientes", params=params).json())

    assert nomes(grupo="Familia Souza") == ["Ana Souza", "Bia Souza"]
    assert nomes(telefone="41999990003") == ["Caio Lima"]
    assert nomes(grupo="Familia Souza", telefone="41999990002") == ["Bia Souza"]  # os filtros se somam
    assert nomes(grupo="Inexistente") == []


def test_painel_filtra_por_resultado_geral(client):
    ana = novo_cliente(client, "Ana Souza")
    bia = novo_cliente(client, "Bia Lima")
    aprovado = novo_obt(client, ana["id"])
    novo_obt(client, bia["id"])  # sem resultado: continua "Processando"
    client.patch(f"/solicitantes/{aprovado['solicitantes'][0]['id']}", json={"resultado": "Aprovado"})

    def clientes(resultado):
        return [p["cliente"] for p in client.get("/painel", params={"resultado_geral": resultado}).json()]

    assert clientes("Aprovado") == ["Ana Souza"]
    assert clientes("Processando") == ["Bia Lima"]
    assert clientes("Negado") == []


# ---------------------------------------------------------------- campos que não aceitam null

def test_solicitante_nao_aceita_campo_nulo_na_edicao(client):
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"])
    titular = processo["solicitantes"][0]
    resposta = client.patch(f"/solicitantes/{titular['id']}", json={"nome": None})
    assert resposta.status_code == 422
    # nada foi gravado: o nome continua o mesmo
    assert client.get(f"/processos/{processo['id']}/solicitantes").json()[0]["nome"] == titular["nome"]


def test_formulario_ds160_nao_aceita_status_nulo(client):
    cliente = novo_cliente(client)
    titular = novo_obt(client, cliente["id"])["solicitantes"][0]
    formulario = client.post(f"/solicitantes/{titular['id']}/formularios-ds160", json={"codigo": "AA00ABC123"}).json()
    resposta = client.patch(f"/formularios-ds160/{formulario['id']}", json={"status": None})
    assert resposta.status_code == 422
    assert client.patch(f"/formularios-ds160/{formulario['id']}", json={"observacao": None}).status_code == 200


# ---------------------------------------------------------------- administração de usuários

def test_admin_consulta_um_usuario_pelo_id(client, como):  # noqa: F811
    leitor = como("leitor")
    resposta = client.get(f"/usuarios/{leitor.usuario.id}")
    assert resposta.status_code == 200
    assert resposta.json()["email"] == leitor.usuario.email
    assert "senha" not in resposta.text  # nem a senha nem o hash saem da API
    assert client.get("/usuarios/999").status_code == 404
    assert leitor.get(f"/usuarios/{leitor.usuario.id}").status_code == 403  # só admin administra


def test_trocar_para_perfil_inexistente_da_422_e_nao_muda_nada(client, como):  # noqa: F811
    atendente = como("atendente")
    resposta = client.patch(f"/usuarios/{atendente.usuario.id}", json={"perfil": "chefe"})
    assert resposta.status_code == 422
    assert "chefe" in resposta.json()["detail"]
    assert client.get(f"/usuarios/{atendente.usuario.id}").json()["perfil"] == "atendente"
    assert client.get(f"/usuarios/{atendente.usuario.id}/auditoria").json() == []  # nada a auditar


def test_admin_redefine_senha_de_outro_usuario_e_a_regra_de_tamanho_vale(client, como, client_anonimo):  # noqa: F811
    alvo = como("admin")
    url = f"/usuarios/{alvo.usuario.id}/senha"
    assert client.post(url, json={"senha": "curta"}).status_code == 422
    assert client.post(url, json={"senha": "outra-senha-bem-longa-9"}).status_code == 204
    # a senha antiga deixou de valer; a nova entra
    antigo = client_anonimo.post("/auth/login", json={"email": alvo.usuario.email, "senha": "senha-de-teste-123"})
    novo = client_anonimo.post("/auth/login", json={"email": alvo.usuario.email, "senha": "outra-senha-bem-longa-9"})
    assert (antigo.status_code, novo.status_code) == (401, 200)
    assert client.post("/usuarios/999/senha", json={"senha": "outra-senha-bem-longa-9"}).status_code == 404
