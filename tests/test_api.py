"""Testes da API contra o PostgreSQL de teste: o que a API recebe, grava e devolve."""
import pytest


def novo_cliente(client, nome="Ana Souza", **extra):
    resposta = client.post("/clientes", json={"nome": nome, **extra})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def novo_obt(client, cliente_id, **extra):
    corpo = {"cliente_id": cliente_id, "situacao": "Processando", **extra}
    resposta = client.post("/processos-obt", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


# ---------------------------------------------------------------- clientes

def test_cliente_telefone_e_normalizado(client):
    criado = novo_cliente(client, telefone="+55 (41) 99999-8888")
    assert criado["telefone"] == "41999998888"


def test_nome_de_cliente_repetido_da_409(client):
    novo_cliente(client, "Ana Souza")
    assert client.post("/clientes", json={"nome": "ANA SOUZA"}).status_code == 409


def test_busca_por_nome_trata_percentual_como_texto(client):
    novo_cliente(client, "Ana Souza")
    novo_cliente(client, "Bia 100% Lima")
    assert [c["nome"] for c in client.get("/clientes", params={"nome": "%"}).json()] == ["Bia 100% Lima"]
    assert [c["nome"] for c in client.get("/clientes", params={"nome": "SOUZA"}).json()] == ["Ana Souza"]


def test_patch_de_cliente_valida_e_grava(client):
    criado = novo_cliente(client)
    resposta = client.patch(f"/clientes/{criado['id']}", json={"grupo": "Familia Souza"})
    assert resposta.json()["grupo"] == "Familia Souza"
    assert client.patch(f"/clientes/{criado['id']}", json={"nome": "  "}).status_code == 422
    assert client.patch("/clientes/999", json={"grupo": "x"}).status_code == 404


def test_cliente_com_processo_nao_pode_ser_apagado(client):
    cliente = novo_cliente(client)
    novo_obt(client, cliente["id"])
    assert client.delete(f"/clientes/{cliente['id']}").status_code == 409
    outro = novo_cliente(client, "Sem Processo")
    assert client.delete(f"/clientes/{outro['id']}").status_code == 204


# ---------------------------------------------------------------- processos

def test_criar_processo_cria_titular_extras_e_evento(client, sessao):
    cliente = novo_cliente(client, "Ana Souza")
    processo = novo_obt(client, cliente["id"], solicitantes_extras=["Filho 1", "Filho 2"])
    assert [(s["nome"], s["titular"]) for s in processo["solicitantes"]] == [
        ("Ana Souza", True), ("Filho 1", False), ("Filho 2", False)]

    from sqlalchemy import select
    from app.models import Evento
    eventos = sessao.scalars(select(Evento)).all()
    assert [(e.tipo.value, e.situacao_nova) for e in eventos] == [("criado", "Processando")]


def test_processo_recusa_situacao_de_outro_tipo(client):
    cliente = novo_cliente(client)
    resposta = client.post("/processos-obt", json={"cliente_id": cliente["id"], "situacao": "Pix"})
    assert resposta.status_code == 422


def test_processo_de_cliente_inexistente_da_422(client):
    assert client.post("/processos-obt", json={"cliente_id": 999, "situacao": "Pago"}).status_code == 422


def test_regras_entre_campos_na_criacao(client):
    cliente = novo_cliente(client)
    base = {"cliente_id": cliente["id"], "situacao": "Processando"}
    assert client.post("/processos-obt", json={**base, "orientacao": "Agendada"}).status_code == 422
    assert client.post("/processos-obt", json={**base, "data_casv": "2026-12-01"}).status_code == 422
    assert client.post("/processos-obt", json={**base, "data_casv": "2026-12-01", "consulado": "SP"}).status_code == 201


def test_consulado_pode_ficar_vazio_sem_data(client):
    cliente = novo_cliente(client)
    assert novo_obt(client, cliente["id"])["consulado"] is None


def test_patch_revalida_o_processo_inteiro(client):
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"])
    url = f"/processos-obt/{processo['id']}"
    # sozinha, a data é válida; junto com o que já está gravado (sem consulado), não é
    assert client.patch(url, json={"data_casv": "2026-12-01"}).status_code == 422
    assert client.patch(url, json={"data_casv": "2026-12-01", "consulado": "RIO"}).status_code == 200
    assert client.get(url).json()["consulado"] == "RIO"


def test_patch_nao_muda_situacao(client):
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"])
    # a situação muda por rota própria (etapa 4), que registra o evento
    assert client.patch(f"/processos-obt/{processo['id']}", json={"situacao": "Pago"}).status_code == 422


def test_renovacao_devolve_data_despacho_calculada(client):
    cliente = novo_cliente(client)
    resposta = client.post("/processos-ren", json={
        "cliente_id": cliente["id"], "situacao": "Cadastro", "consulado": "RIO", "data_casv": "2026-10-16"})
    assert resposta.status_code == 201
    assert resposta.json()["data_despacho"] == "2026-10-09"


def test_id_de_outro_tipo_da_404(client):
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"])
    assert client.get(f"/processos-ren/{processo['id']}").status_code == 404
    assert client.get(f"/processos-obt/{processo['id']}").status_code == 200


def test_nova_tentativa_do_mesmo_cliente(client):
    cliente = novo_cliente(client)
    primeiro = novo_obt(client, cliente["id"])
    segundo = novo_obt(client, cliente["id"], processo_anterior_id=primeiro["id"])
    assert segundo["processo_anterior_id"] == primeiro["id"]
    outro = novo_cliente(client, "Outra Pessoa")
    resposta = client.post("/processos-obt", json={
        "cliente_id": outro["id"], "situacao": "Pago", "processo_anterior_id": primeiro["id"]})
    assert resposta.status_code == 422


def test_listar_com_filtros(client):
    ana = novo_cliente(client, "Ana")
    bia = novo_cliente(client, "Bia")
    novo_obt(client, ana["id"], consulado="SP")
    novo_obt(client, bia["id"], situacao="Pago")
    assert len(client.get("/processos-obt").json()) == 2
    assert len(client.get("/processos-obt", params={"cliente_id": bia["id"]}).json()) == 1
    assert len(client.get("/processos-obt", params={"situacao": "Pago"}).json()) == 1
    assert len(client.get("/processos-obt", params={"consulado": "SP"}).json()) == 1
    assert client.get("/processos-pass", params={"consulado": "SP"}).status_code == 422


def test_apagar_processo_leva_junto_solicitantes_e_formularios(client, sessao):
    from sqlalchemy import select
    from app.models import FormularioDS160, Solicitante
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"])
    titular = processo["solicitantes"][0]
    client.post(f"/solicitantes/{titular['id']}/formularios-ds160", json={"codigo": "AA00ABC123"})
    assert client.delete(f"/processos-obt/{processo['id']}").status_code == 204
    assert client.get(f"/processos-obt/{processo['id']}").status_code == 404
    assert sessao.scalars(select(Solicitante)).all() == []
    assert sessao.scalars(select(FormularioDS160)).all() == []


# ---------------------------------------------------------------- solicitantes e DS-160

def test_adicionar_e_atualizar_solicitante(client):
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"])
    criado = client.post(f"/processos/{processo['id']}/solicitantes", json={"nome": "Filho"}).json()
    assert criado["titular"] is False
    resposta = client.patch(f"/solicitantes/{criado['id']}", json={"resultado": "Negado"})
    assert resposta.json()["resultado"] == "Negado"
    assert len(client.get(f"/processos/{processo['id']}/solicitantes").json()) == 2


def test_trocar_titular_mantem_so_um(client):
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"], solicitantes_extras=["Filho"])
    filho = processo["solicitantes"][1]
    resposta = client.post(f"/solicitantes/{filho['id']}/titular")
    assert resposta.status_code == 200 and resposta.json()["titular"] is True
    titulares = [s for s in client.get(f"/processos/{processo['id']}/solicitantes").json() if s["titular"]]
    assert [s["nome"] for s in titulares] == ["Filho"]


def test_titular_nao_pode_ser_removido(client):
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"], solicitantes_extras=["Filho"])
    titular, filho = processo["solicitantes"]
    assert client.delete(f"/solicitantes/{titular['id']}").status_code == 409
    assert client.delete(f"/solicitantes/{filho['id']}").status_code == 204


@pytest.mark.parametrize("codigo", ["AA00ABC12", "AA00ABC1234", "BB00ABC123", "AA00ab-123"])
def test_codigo_ds160_fora_do_padrao_da_422(client, codigo):
    cliente = novo_cliente(client)
    titular = novo_obt(client, cliente["id"])["solicitantes"][0]
    resposta = client.post(f"/solicitantes/{titular['id']}/formularios-ds160", json={"codigo": codigo})
    assert resposta.status_code == 422


def test_ds160_cadastro_edicao_duplicidade_e_remocao(client):
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"], solicitantes_extras=["Filho"])
    titular, filho = processo["solicitantes"]
    url = f"/solicitantes/{titular['id']}/formularios-ds160"

    criado = client.post(url, json={"codigo": "aa00abc123"}).json()  # normaliza para maiúsculas
    assert criado["codigo"] == "AA00ABC123" and criado["status"] == "Pendente"
    # o mesmo código não pode ir para outra pessoa
    assert client.post(f"/solicitantes/{filho['id']}/formularios-ds160",
                       json={"codigo": "AA00ABC123"}).status_code == 409
    # a mesma pessoa pode ter vários formulários (refeito)
    assert client.post(url, json={"codigo": "AA00XYZ999"}).status_code == 201

    editado = client.patch(f"/formularios-ds160/{criado['id']}", json={"status": "Revisado", "observacao": "ok"})
    assert editado.json()["status"] == "Revisado"
    assert client.patch(f"/formularios-ds160/{criado['id']}", json={"codigo": "AA00NOVO12"}).status_code == 422

    visto = client.get(f"/processos-obt/{processo['id']}").json()["solicitantes"][0]
    assert [f["codigo"] for f in visto["formularios"]] == ["AA00ABC123", "AA00XYZ999"]
    assert client.delete(f"/formularios-ds160/{criado['id']}").status_code == 204


# ---------------------------------------------------------------- painel

def test_painel_mostra_uma_linha_por_processo_como_a_planilha(client):
    ana = novo_cliente(client, "Ana Souza", telefone="41999999999")
    processo = novo_obt(client, ana["id"], consulado="SP", data_casv="2026-12-01",
                        solicitantes_extras=["Filho 1", "Filho 2"])
    titular = processo["solicitantes"][0]
    client.post(f"/solicitantes/{titular['id']}/formularios-ds160", json={"codigo": "AA00ABC123"})
    client.post(f"/solicitantes/{processo['solicitantes'][1]['id']}/formularios-ds160", json={"codigo": "AA00ABC124"})

    bia = novo_cliente(client, "Bia Lima")
    client.post("/processos-ren", json={"cliente_id": bia["id"], "situacao": "Cadastro",
                                        "consulado": "RIO", "data_casv": "2026-10-16"})

    linhas = client.get("/painel").json()
    assert len(linhas) == 2  # um por processo, mesmo com 3 solicitantes e 2 formulários

    obt = next(l for l in linhas if l["tipo"] == "OBT")
    assert obt["cliente"] == "Ana Souza" and obt["titular"] == "Ana Souza"
    assert obt["n_solicitantes"] == 3
    assert obt["solicitantes"] == "Ana Souza, Filho 1, Filho 2"
    assert obt["n_formularios"] == 2
    assert obt["consulado"] == "SP" and obt["data_casv"] == "2026-12-01"
    assert obt["resultado_geral"] == "Processando"

    ren = next(l for l in linhas if l["tipo"] == "REN")
    assert ren["n_solicitantes"] == 1 and ren["data_despacho"] == "2026-10-09" and ren["n_formularios"] == 0


def test_painel_resultado_geral_resume_o_grupo(client):
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"], solicitantes_extras=["Filho"])
    titular, filho = processo["solicitantes"]
    client.patch(f"/solicitantes/{titular['id']}", json={"resultado": "Aprovado"})
    assert client.get("/painel").json()[0]["resultado_geral"] == "Processando"  # falta o filho
    client.patch(f"/solicitantes/{filho['id']}", json={"resultado": "Negado"})
    assert client.get("/painel").json()[0]["resultado_geral"] == "Parcial"
    client.patch(f"/solicitantes/{filho['id']}", json={"resultado": "Aprovado"})
    assert client.get("/painel").json()[0]["resultado_geral"] == "Aprovado"


def test_painel_filtros(client):
    ana = novo_cliente(client, "Ana Souza")
    bia = novo_cliente(client, "Bia Lima")
    novo_obt(client, ana["id"], consulado="SP")
    client.post("/processos-pass", json={"cliente_id": bia["id"], "situacao": "Pendente", "data_pf": "2026-11-20"})
    assert len(client.get("/painel", params={"tipo": "PASS"}).json()) == 1
    assert client.get("/painel", params={"tipo": "PASS"}).json()[0]["data_pf"] == "2026-11-20"
    assert len(client.get("/painel", params={"cliente": "souza"}).json()) == 1
    assert len(client.get("/painel", params={"consulado": "SP"}).json()) == 1
    assert len(client.get("/painel", params={"situacao": "Pendente"}).json()) == 1
    assert client.get("/painel", params={"tipo": "XXX"}).status_code == 422
