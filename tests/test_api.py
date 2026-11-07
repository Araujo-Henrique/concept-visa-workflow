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


def test_painel_informa_o_total_para_paginar(client):
    ana = novo_cliente(client, "Ana Souza")
    for _ in range(3):
        novo_obt(client, ana["id"])
    resposta = client.get("/painel", params={"limit": 2})
    assert len(resposta.json()) == 2
    assert resposta.headers["X-Total-Count"] == "3"  # o total ignora limit/offset, mas respeita os filtros
    assert client.get("/painel", params={"tipo": "REN"}).headers["X-Total-Count"] == "0"


def test_painel_filtra_por_id_do_processo(client):
    ana = novo_cliente(client, "Ana Souza")
    primeiro, _ = novo_obt(client, ana["id"]), novo_obt(client, ana["id"])
    linhas = client.get("/painel", params={"processo_id": primeiro["id"]}).json()
    assert [l["processo_id"] for l in linhas] == [primeiro["id"]]


def test_painel_filtra_por_periodo_de_uma_data(client):
    ana = novo_cliente(client, "Ana Souza")
    dentro = novo_obt(client, ana["id"], consulado="SP", data_casv="2026-12-05", data_entrevista="2027-01-10")
    novo_obt(client, ana["id"], consulado="SP", data_casv="2027-02-01")
    novo_obt(client, ana["id"])  # sem data: fica de fora de qualquer período
    params = {"data": "casv", "de": "2026-12-01", "ate": "2026-12-31"}
    resposta = client.get("/painel", params=params)
    assert [l["processo_id"] for l in resposta.json()] == [dentro["id"]] and resposta.headers["X-Total-Count"] == "1"
    # só o início ou só o fim também valem
    assert len(client.get("/painel", params={"data": "casv", "de": "2027-01-01"}).json()) == 1
    assert len(client.get("/painel", params={"data": "entrevista", "ate": "2027-01-31"}).json()) == 1
    # período sem dizer qual data, data desconhecida ou período invertido: 422
    assert client.get("/painel", params={"de": "2026-12-01"}).status_code == 422
    assert client.get("/painel", params={"data": "nascimento", "de": "2026-12-01"}).status_code == 422
    assert client.get("/painel", params={"data": "casv", "de": "2026-12-31", "ate": "2026-12-01"}).status_code == 422


def test_resumo_conta_por_tipo_situacao_e_resultado(client):
    ana = novo_cliente(client, "Ana Souza")
    novo_obt(client, ana["id"])
    novo_obt(client, ana["id"])
    client.post("/processos-pass", json={"cliente_id": ana["id"], "situacao": "Pendente"})
    resumo = client.get("/painel/resumo").json()
    assert resumo["OBT"] == {"total": 2, "por_situacao": {"Processando": 2}, "por_resultado": {"Processando": 2}}
    assert resumo["PASS"]["total"] == 1 and resumo["PASS"]["por_situacao"] == {"Pendente": 1}
    assert resumo["REN"] == {"total": 0, "por_situacao": {}, "por_resultado": {}}  # todo tipo aparece


def test_agenda_lista_as_datas_do_periodo_em_ordem(client):
    ana = novo_cliente(client, "Ana Souza")
    obt = novo_obt(client, ana["id"], consulado="SP", data_casv="2026-11-10", data_entrevista="2026-11-12",
                   orientacao="Agendada", orientacao_data="2026-11-03")
    client.post("/processos-ren", json={"cliente_id": ana["id"], "situacao": "Cadastro", "consulado": "RIO",
                                        "data_casv": "2026-11-20"})  # despacho 13/11
    client.post("/processos-pass", json={"cliente_id": ana["id"], "situacao": "Pendente", "data_pf": "2026-12-25"})

    agenda = client.get("/painel/agenda", params={"de": "2026-11-01", "ate": "2026-11-30"}).json()
    assert [(a["data"], a["evento"], a["tipo"]) for a in agenda] == [
        ("2026-11-03", "orientacao", "OBT"), ("2026-11-10", "casv", "OBT"), ("2026-11-12", "entrevista", "OBT"),
        ("2026-11-13", "despacho", "REN"), ("2026-11-20", "casv", "REN")]  # o PF de dezembro fica de fora
    assert agenda[0]["processo_id"] == obt["id"] and agenda[0]["cliente"] == "Ana Souza"
    assert agenda[0]["consulado"] == "SP" and agenda[0]["situacao"] == "Processando"


def test_agenda_recusa_periodo_invertido_ou_longo_demais(client):
    assert client.get("/painel/agenda", params={"de": "2026-11-30", "ate": "2026-11-01"}).status_code == 422
    assert client.get("/painel/agenda", params={"de": "2026-01-01", "ate": "2026-12-31"}).status_code == 422


def test_referencias_trazem_as_situacoes_na_ordem_do_fluxo(client):
    ref = client.get("/referencias").json()
    assert ref["situacoes"]["PASS"][0] == "Pendente" and ref["situacoes"]["OBT"][-1] == "Concluido"
    assert "Pix" in ref["situacoes"]["PASS"] and "Pix" not in ref["situacoes"]["OBT"]
    assert ref["consulados"] == ["POA", "RIO", "BSB", "SP", "REC"] and ref["perfis"] == ["admin", "atendente", "leitor"]


def test_painel_cada_tipo_mostra_so_os_campos_que_lhe_pertencem(client):
    ana = novo_cliente(client, "Ana Souza")
    novo_obt(client, ana["id"], consulado="SP", data_casv="2026-12-01")
    client.post("/processos-ren", json={"cliente_id": ana["id"], "situacao": "Cadastro"})
    client.post("/processos-pass", json={"cliente_id": ana["id"], "situacao": "Pendente", "data_pf": "2026-11-20"})

    por_tipo = {linha["tipo"]: linha for linha in client.get("/painel").json()}
    assert "data_pf" not in por_tipo["OBT"] and "prazo_pf" not in por_tipo["OBT"]
    assert "data_despacho" not in por_tipo["OBT"] and "data_entrevista" in por_tipo["OBT"]
    assert "data_entrevista" not in por_tipo["REN"] and "data_despacho" in por_tipo["REN"]
    assert "consulado" not in por_tipo["PASS"] and "codigo_rastreio" not in por_tipo["PASS"]
    assert por_tipo["PASS"]["data_pf"] == "2026-11-20"
    # campo do tipo, mesmo vazio, continua aparecendo (o front não precisa adivinhar se faltou)
    assert por_tipo["REN"]["consulado"] is None and "consulado" in por_tipo["REN"]


def test_painel_obt_mostra_a_orientacao_com_o_nome_de_quem_orientou(client, sessao):
    from app.models import Perfil, Usuario
    from sqlalchemy import select
    perfil = sessao.scalars(select(Perfil).where(Perfil.nome == "atendente")).one()
    gabriel = Usuario(nome="Gabriel Vieira", email="gabriel@exemplo.com", perfil_id=perfil.id)
    sessao.add(gabriel)
    sessao.commit()

    ana = novo_cliente(client, "Ana Souza")
    novo_obt(client, ana["id"], consulado="SP", solicitantes_extras=["Filho"], orientacao="Agendada",
             orientacao_data="2026-11-10", orientacao_por_id=gabriel.id)
    bia = novo_cliente(client, "Bia Lima")
    novo_obt(client, bia["id"])  # sem orientação indicada

    linhas = {l["cliente"]: l for l in client.get("/painel").json()}
    ana_obt = linhas["Ana Souza"]
    assert (ana_obt["orientacao"], ana_obt["orientacao_data"], ana_obt["orientacao_por"]) == (
        "Agendada", "2026-11-10", "Gabriel Vieira")
    assert ana_obt["n_solicitantes"] == 2  # o JOIN com usuarios não duplica a contagem
    assert (linhas["Bia Lima"]["orientacao"], linhas["Bia Lima"]["orientacao_por"]) == ("Pendente", None)

    # só o OBT tem orientação
    client.post("/processos-ren", json={"cliente_id": ana["id"], "situacao": "Cadastro"})
    ren = next(l for l in client.get("/painel", params={"tipo": "REN"}).json())
    assert "orientacao" not in ren


# ---------------------------------------------------------------- histórico importado

def test_obt_do_historico_com_data_e_sem_consulado_continua_legivel(client, sessao):
    """Os 'N/D' da planilha viraram consulado vazio, alguns com data marcada. O banco aceita (de propósito);
    a regra 'com data, informe o consulado' vale ao criar e editar, nunca para LER o que já está gravado."""
    from datetime import date

    from app.enums import Orientacao, Rascunho
    from app.models import ProcessoOBT, Solicitante
    ana = novo_cliente(client, "Ana Souza")
    antigo = ProcessoOBT(cliente_id=ana["id"], situacao="Concluido", consulado=None, data_casv=date(2024, 3, 3),
                         data_entrevista=date(2024, 3, 4), status_rascunho=Rascunho.ENVIADO,
                         orientacao=Orientacao.FORNECIDAS)
    antigo.solicitantes.append(Solicitante(nome="Ana Souza", titular=True))
    sessao.add(antigo)
    sessao.commit()

    resposta = client.get(f"/processos-obt/{antigo.id}")
    assert resposta.status_code == 200
    assert (resposta.json()["consulado"], resposta.json()["data_casv"]) == (None, "2024-03-03")
    assert client.get("/processos-obt", params={"cliente_id": ana["id"]}).status_code == 200

    # a regra continua valendo para quem cria
    assert client.post("/processos-obt", json={"cliente_id": ana["id"], "situacao": "Processando",
                                               "data_casv": "2026-12-01"}).status_code == 422


def _obt_do_historico(client, sessao):
    """OBT como os importados: data marcada e consulado vazio (era 'N/D')."""
    from datetime import date

    from app.enums import Orientacao, Rascunho
    from app.models import ProcessoOBT, Solicitante
    ana = novo_cliente(client, "Ana Historico")
    antigo = ProcessoOBT(cliente_id=ana["id"], situacao="Concluido", consulado=None, data_casv=date(2024, 3, 3),
                         status_rascunho=Rascunho.ENVIADO, orientacao=Orientacao.FORNECIDAS)
    antigo.solicitantes.append(Solicitante(nome="Ana Historico", titular=True))
    sessao.add(antigo)
    sessao.commit()
    return antigo.id


def test_historico_pode_ser_editado_sem_preencher_o_consulado(client, sessao):
    pid = _obt_do_historico(client, sessao)
    r = client.patch(f"/processos-obt/{pid}", json={"observacao": "conferido", "codigo_rastreio": "BR123"})
    assert r.status_code == 200 and r.json()["observacao"] == "conferido" and r.json()["consulado"] is None


def test_mexer_nas_datas_do_historico_continua_exigindo_o_consulado(client, sessao):
    pid = _obt_do_historico(client, sessao)
    assert client.patch(f"/processos-obt/{pid}", json={"data_entrevista": "2024-03-04"}).status_code == 422
    assert client.patch(f"/processos-obt/{pid}", json={"consulado": "SP"}).status_code == 200  # corrige
    assert client.patch(f"/processos-obt/{pid}", json={"data_entrevista": "2024-03-04"}).status_code == 200


def test_nao_da_para_apagar_o_consulado_de_um_processo_com_data(client):
    ana = novo_cliente(client, "Ana Atual")
    p = novo_obt(client, ana["id"], consulado="SP", data_casv="2026-12-01")
    assert client.patch(f"/processos-obt/{p['id']}", json={"consulado": None}).status_code == 422


# ---------------------------------------------------------------- clientes na tela

def test_lista_de_clientes_em_ordem_alfabetica_com_total_e_numero_de_processos(client):
    bia, ana = novo_cliente(client, "Bia Lima"), novo_cliente(client, "ana Souza")
    novo_obt(client, ana["id"])
    novo_obt(client, ana["id"])
    resposta = client.get("/clientes", params={"limit": 1})
    assert resposta.headers["X-Total-Count"] == "2"
    assert [(c["nome"], c["n_processos"]) for c in resposta.json()] == [("ana Souza", 2)]  # sem diferenciar caixa
    assert client.get("/clientes", params={"offset": 1}).json()[0]["n_processos"] == 0


def test_busca_unica_por_nome_email_ou_telefone(client):
    novo_cliente(client, "Ana Souza", email="ana@exemplo.com", telefone="(41) 99999-0001")
    novo_cliente(client, "Bia Lima", email="bia@outro.com", telefone="41988880002")
    busca = lambda termo: [c["nome"] for c in client.get("/clientes", params={"busca": termo}).json()]
    assert busca("souza") == ["Ana Souza"]
    assert busca("OUTRO.com") == ["Bia Lima"]
    assert busca("9999-0001") == ["Ana Souza"]  # telefone: só os dígitos contam
    assert busca("41 9") == ["Ana Souza", "Bia Lima"]
    assert client.get("/clientes", params={"busca": "souza"}).headers["X-Total-Count"] == "1"


def test_painel_filtra_pelo_cliente(client):
    ana, bia = novo_cliente(client, "Ana Souza"), novo_cliente(client, "Bia Lima")
    novo_obt(client, ana["id"])
    novo_obt(client, bia["id"])
    linhas = client.get("/painel", params={"cliente_id": ana["id"]}).json()
    assert [l["cliente"] for l in linhas] == ["Ana Souza"]


def test_referencias_trazem_os_usuarios_ativos_para_orientacao(client, sessao, usuario_teste):
    from app.servicos.usuarios import criar_usuario
    inativo = criar_usuario(sessao, "Fora Daqui", "fora@exemplo.com", "leitor", "senha-bem-longa-1")
    inativo.ativo = False
    sessao.commit()
    usuarios = client.get("/referencias").json()["usuarios"]
    assert usuarios == [{"id": usuario_teste.id, "nome": "Usuario Teste"}]  # sem e-mail, sem inativos
