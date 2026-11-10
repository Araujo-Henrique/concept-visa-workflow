"""Clientes excluídos: restaurar (volta idêntico) e eliminar definitivamente (não sobra nenhum dado pessoal).

A exclusão comum agora é do atendente também, e é segura porque o admin restaura. A eliminação definitiva é
manual, só do admin, e só de quem já foi excluído.
"""
import pytest
from sqlalchemy import text

from tests.test_api import novo_cliente, novo_obt
from tests.test_autorizacao import como  # noqa: F401  (fixture)

TABELAS_DO_CLIENTE = ("clientes", "processos", "processo_obt", "processo_ren", "processo_pass", "solicitantes",
                      "formularios_ds160", "eventos")


def _foto(sessao, cliente_id):
    """Tudo o que existe do cliente, linha a linha, para comparar antes e depois."""
    sessao.expire_all()
    consultas = {
        "clientes": "SELECT * FROM clientes WHERE id = :c ORDER BY id",
        "processos": "SELECT * FROM processos WHERE cliente_id = :c ORDER BY id",
        "processo_obt": "SELECT d.* FROM processo_obt d JOIN processos p ON p.id = d.processo_id "
                        "WHERE p.cliente_id = :c ORDER BY d.processo_id",
        "processo_ren": "SELECT d.* FROM processo_ren d JOIN processos p ON p.id = d.processo_id "
                        "WHERE p.cliente_id = :c ORDER BY d.processo_id",
        "processo_pass": "SELECT d.* FROM processo_pass d JOIN processos p ON p.id = d.processo_id "
                         "WHERE p.cliente_id = :c ORDER BY d.processo_id",
        "solicitantes": "SELECT s.* FROM solicitantes s JOIN processos p ON p.id = s.processo_id "
                        "WHERE p.cliente_id = :c ORDER BY s.id",
        "formularios_ds160": "SELECT f.* FROM formularios_ds160 f JOIN solicitantes s ON s.id = f.solicitante_id "
                             "JOIN processos p ON p.id = s.processo_id WHERE p.cliente_id = :c ORDER BY f.id",
        "eventos": "SELECT e.* FROM eventos e JOIN processos p ON p.id = e.processo_id "
                   "WHERE p.cliente_id = :c ORDER BY e.id",
    }
    return {t: [dict(r) for r in sessao.execute(text(q), {"c": cliente_id}).mappings()] for t, q in consultas.items()}


def _cliente_completo(client, nome="Ana Souza"):
    """Cliente com 2 processos (o 2º é nova tentativa do 1º), pessoas, DS-160 e mudanças de situação."""
    cliente = novo_cliente(client, nome=nome, telefone="41999998888", email="ana@exemplo.com", grupo="Família")
    primeiro = novo_obt(client, cliente["id"], solicitantes_extras=["Bia Souza"], observacao="obs do primeiro")
    titular = next(s for s in primeiro["solicitantes"] if s["titular"])
    client.post(f"/solicitantes/{titular['id']}/formularios-ds160", json={"codigo": "AA00ABC123"})
    client.post(f"/processos/{primeiro['id']}/situacao", json={"situacao": "Pago"})
    segundo = novo_obt(client, cliente["id"], processo_anterior_id=primeiro["id"])
    return cliente, primeiro, segundo


def _excluir(client, cliente):
    assert client.delete(f"/clientes/{cliente['id']}", params={"com_processos": True}).status_code == 204


# ---------------------------------------------------------------- restaurar

def test_restaurar_devolve_o_cliente_identico_ao_que_foi_excluido(client, sessao):
    cliente, primeiro, segundo = _cliente_completo(client)
    antes = _foto(sessao, cliente["id"])
    assert len(antes["eventos"]) >= 3 and antes["formularios_ds160"] and antes["solicitantes"]
    _excluir(client, cliente)
    assert _foto(sessao, cliente["id"])["clientes"] == []

    resposta = client.post(f"/auditoria/apagados/{cliente['id']}/restaurar")
    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {"cliente_id": cliente["id"], "nome": "Ana Souza", "processos": 2, "pessoas": 3,
                               "formularios": 1, "eventos": len(antes["eventos"]), "vinculos": 1}

    depois = _foto(sessao, cliente["id"])
    # TODAS as colunas, inclusive datas, ids, a observação e o vínculo da nova tentativa com a anterior
    assert depois == antes
    assert depois["processos"][1]["processo_anterior_id"] == primeiro["id"]


def test_restaurado_funciona_de_novo_pela_api_normal(client, sessao):
    cliente, primeiro, _ = _cliente_completo(client)
    _excluir(client, cliente)
    client.post(f"/auditoria/apagados/{cliente['id']}/restaurar")
    assert client.get(f"/clientes/{cliente['id']}").json()["nome"] == "Ana Souza"
    assert client.get(f"/processos-obt/{primeiro['id']}").json()["situacao"] == "Pago"
    assert len(client.get(f"/processos/{primeiro['id']}/eventos").json()) == 2  # criado + Pago
    # e continua editável: a sequência de ids não colidiu
    assert client.post("/processos-obt", json={"cliente_id": cliente["id"], "situacao": "Processando"}).status_code == 201
    assert client.post("/clientes", json={"nome": "Outro Cliente"}).status_code == 201


def test_restaurar_religa_a_tentativa_de_outro_cliente_que_apontava_para_o_excluido(client, sessao):
    ana = novo_cliente(client, nome="Ana Souza")
    bia = novo_cliente(client, nome="Bia Souza")
    antigo = novo_obt(client, ana["id"])
    novo = novo_obt(client, bia["id"])
    sessao.execute(text("UPDATE processos SET processo_anterior_id = :a WHERE id = :n"),
                   {"a": antigo["id"], "n": novo["id"]})
    sessao.commit()
    _excluir(client, ana)  # o vínculo da Bia perde a referência
    assert client.get(f"/processos-obt/{novo['id']}").json()["processo_anterior_id"] is None
    resposta = client.post(f"/auditoria/apagados/{ana['id']}/restaurar")
    assert resposta.json()["vinculos"] == 1
    assert client.get(f"/processos-obt/{novo['id']}").json()["processo_anterior_id"] == antigo["id"]


def test_excluir_um_cliente_nao_altera_a_data_de_atualizacao_dos_processos_de_outros(client, sessao):
    # desfazer o vínculo "tentativa anterior" não é uma edição do processo da Bia
    ana = novo_cliente(client, nome="Ana Souza")
    bia = novo_cliente(client, nome="Bia Souza")
    antigo = novo_obt(client, ana["id"])
    novo = novo_obt(client, bia["id"])
    sessao.execute(text("UPDATE processos SET processo_anterior_id = :a WHERE id = :n"),
                   {"a": antigo["id"], "n": novo["id"]})
    sessao.commit()
    data = sessao.scalar(text("SELECT atualizado_em FROM processos WHERE id = :n"), {"n": novo["id"]})
    _excluir(client, ana)
    sessao.expire_all()
    assert sessao.scalar(text("SELECT atualizado_em FROM processos WHERE id = :n"), {"n": novo["id"]}) == data


def test_restauracao_fica_na_auditoria_marcada_como_tal_e_com_o_admin(client, sessao, usuario_teste):
    cliente, _, _ = _cliente_completo(client)
    _excluir(client, cliente)
    client.post(f"/auditoria/apagados/{cliente['id']}/restaurar")
    linhas = sessao.execute(text(
        "SELECT usuario_id, origem FROM auditoria WHERE tabela = 'clientes' AND registro_id = :c "
        "AND acao = 'criou' ORDER BY id DESC LIMIT 1"), {"c": cliente["id"]}).one()
    assert linhas.origem == "restauracao" and linhas.usuario_id == usuario_teste.id


def test_excluir_de_novo_depois_de_restaurar_tambem_pode_ser_restaurado(client, sessao):
    cliente, _, _ = _cliente_completo(client)
    antes = _foto(sessao, cliente["id"])
    _excluir(client, cliente)
    client.post(f"/auditoria/apagados/{cliente['id']}/restaurar")
    _excluir(client, cliente)
    assert client.post(f"/auditoria/apagados/{cliente['id']}/restaurar").status_code == 200
    assert _foto(sessao, cliente["id"]) == antes


def test_nao_restaura_quem_esta_no_sistema(client):
    cliente = novo_cliente(client)
    resposta = client.post(f"/auditoria/apagados/{cliente['id']}/restaurar")
    assert resposta.status_code == 409 and "está no sistema" in resposta.json()["detail"]


def test_nao_restaura_quem_nunca_existiu(client):
    assert client.post("/auditoria/apagados/99999/restaurar").status_code == 404


def test_nome_que_ja_existe_de_novo_barra_a_restauracao_e_nao_muda_nada(client, sessao):
    cliente, _, _ = _cliente_completo(client)
    _excluir(client, cliente)
    novo_cliente(client, nome="ana souza")  # outra pessoa cadastrada com o mesmo nome (sem diferenciar maiúsculas)
    resposta = client.post(f"/auditoria/apagados/{cliente['id']}/restaurar")
    assert resposta.status_code == 409 and "Já existe outro cliente chamado" in resposta.json()["detail"]
    assert _foto(sessao, cliente["id"])["clientes"] == []


def test_dado_unico_em_uso_de_novo_desfaz_tudo_o_que_ja_tinha_sido_recolocado(client, sessao):
    cliente, _, _ = _cliente_completo(client)  # DS-160 AA00ABC123
    _excluir(client, cliente)
    outro = novo_cliente(client, nome="Carla Dias")
    processo = novo_obt(client, outro["id"])
    titular = next(s for s in processo["solicitantes"] if s["titular"])
    # o código ficou livre com a exclusão e foi usado por outro cliente
    assert client.post(f"/solicitantes/{titular['id']}/formularios-ds160", json={"codigo": "AA00ABC123"}).status_code == 201
    resposta = client.post(f"/auditoria/apagados/{cliente['id']}/restaurar")
    assert resposta.status_code == 409 and "Nada foi alterado" in resposta.json()["detail"]
    # tudo ou nada: nem o cliente nem os processos, que entraram antes do DS-160, ficaram para trás
    assert _foto(sessao, cliente["id"])["clientes"] == []
    assert sessao.scalar(text("SELECT count(*) FROM processos WHERE cliente_id = :c"), {"c": cliente["id"]}) == 0


# ---------------------------------------------------------------- lista de excluídos

def test_lista_so_tem_quem_esta_fora_do_sistema_do_mais_novo_ao_mais_antigo(client, usuario_teste):
    a = novo_cliente(client, nome="Ana Souza", telefone="41999998888")
    novo_obt(client, a["id"])
    b = novo_cliente(client, nome="Bia Souza")
    novo_cliente(client, nome="Carla Dias")  # segue no sistema
    _excluir(client, a)
    client.delete(f"/clientes/{b['id']}")
    resposta = client.get("/auditoria/apagados")
    assert resposta.headers["X-Total-Count"] == "2"
    lista = resposta.json()
    assert [c["nome"] for c in lista] == ["Bia Souza", "Ana Souza"]
    assert lista[1]["n_processos"] == 1 and lista[0]["n_processos"] == 0
    assert lista[1]["telefone"] == "41999998888" and lista[1]["apagado_por"] == usuario_teste.nome


def test_restaurado_sai_da_lista(client):
    cliente = novo_cliente(client)
    client.delete(f"/clientes/{cliente['id']}")
    assert len(client.get("/auditoria/apagados").json()) == 1
    client.post(f"/auditoria/apagados/{cliente['id']}/restaurar")
    assert client.get("/auditoria/apagados").json() == []


def test_cliente_excluido_duas_vezes_aparece_uma_so_vez(client):
    cliente = novo_cliente(client)
    client.delete(f"/clientes/{cliente['id']}")
    client.post(f"/auditoria/apagados/{cliente['id']}/restaurar")
    client.delete(f"/clientes/{cliente['id']}")
    assert len(client.get("/auditoria/apagados").json()) == 1


def test_atendente_exclui_e_o_admin_enxerga_e_restaura(como):
    admin, atendente = como("admin"), como("atendente")
    cliente = novo_cliente(atendente, nome="Excluido Por Engano")
    novo_obt(atendente, cliente["id"])
    assert atendente.delete(f"/clientes/{cliente['id']}", params={"com_processos": True}).status_code == 204
    [item] = admin.get("/auditoria/apagados").json()
    assert item["nome"] == "Excluido Por Engano" and item["apagado_por"] == atendente.usuario.nome
    assert admin.post(f"/auditoria/apagados/{cliente['id']}/restaurar").status_code == 200


# ---------------------------------------------------------------- eliminar definitivamente

def _tudo_que_o_banco_sabe(sessao):
    """Todo o texto de todas as tabelas, para procurar rastro de dado pessoal em qualquer lugar."""
    sessao.expire_all()
    partes = []
    for tabela in TABELAS_DO_CLIENTE + ("auditoria", "chaves_idempotencia"):
        for linha in sessao.execute(text(f"SELECT t::text FROM {tabela} t")):
            partes.append(linha[0])
    return "\n".join(partes)


DADOS_PESSOAIS = ("Ana Souza", "Bia Souza", "41999998888", "ana@exemplo.com", "Família", "AA00ABC123",
                  "obs do primeiro")


def test_eliminar_nao_deixa_nenhum_dado_pessoal_em_tabela_nenhuma(client, sessao):
    cliente, _, _ = _cliente_completo(client)
    _excluir(client, cliente)
    assert all(d in _tudo_que_o_banco_sabe(sessao) for d in ("Ana Souza", "41999998888", "AA00ABC123"))  # sanidade

    resposta = client.post(f"/auditoria/apagados/{cliente['id']}/eliminar",
                           json={"nome_confirmado": "  ana   SOUZA ", "motivo": "Pedido do titular por e-mail"})
    assert resposta.status_code == 200 and resposta.json()["linhas_removidas"] > 10

    rastro = _tudo_que_o_banco_sabe(sessao)
    for dado in DADOS_PESSOAIS:
        assert dado not in rastro, f"sobrou '{dado}' no banco"
    assert client.get("/auditoria/apagados").json() == []
    assert client.post(f"/auditoria/apagados/{cliente['id']}/restaurar").status_code == 404  # sem volta


def test_eliminar_deixa_so_a_lapide_sem_dado_pessoal(client, sessao, usuario_teste):
    cliente, _, _ = _cliente_completo(client)
    _excluir(client, cliente)
    client.post(f"/auditoria/apagados/{cliente['id']}/eliminar",
                json={"nome_confirmado": "Ana Souza", "motivo": "Pedido do titular"})
    linhas = list(sessao.execute(text(
        "SELECT tabela, registro_id, cliente_id, acao, antes, depois, usuario_id, origem FROM auditoria "
        "WHERE cliente_id = :c OR registro_id = :c"), {"c": cliente["id"]}).mappings())
    assert len(linhas) == 1
    lapide = linhas[0]
    assert (lapide["tabela"], lapide["acao"], lapide["antes"]) == ("clientes", "eliminou", None)
    assert lapide["usuario_id"] == usuario_teste.id
    assert lapide["depois"]["motivo"] == "Pedido do titular" and lapide["depois"]["processos"] == 2
    # e a lápide é legível pela API (quem eliminou, quando, por quê)
    [item] = client.get("/auditoria", params={"tabela": "clientes", "acao": "eliminou"}).json()
    assert item["usuario_nome"] == usuario_teste.nome and item["depois"]["motivo"] == "Pedido do titular"


def test_eliminar_leva_tambem_linhas_orfas_que_so_sabem_o_processo(client, sessao):
    # rede de segurança: uma linha de auditoria sem cliente_id (o trigger não achou o dono) mas com o processo
    # dele ainda carrega dado pessoal e precisa sair junto
    cliente, primeiro, _ = _cliente_completo(client)
    _excluir(client, cliente)
    sessao.execute(text(
        "INSERT INTO auditoria (tabela, registro_id, processo_id, cliente_id, acao, antes, origem) "
        "VALUES ('solicitantes', 9999, :p, NULL, 'apagou', CAST(:j AS jsonb), 'banco')"),
        {"p": primeiro["id"], "j": '{"nome": "Pessoa Orfa Sigilosa"}'})
    sessao.commit()
    client.post(f"/auditoria/apagados/{cliente['id']}/eliminar", json={"nome_confirmado": "Ana Souza", "motivo": "Teste"})
    assert "Pessoa Orfa Sigilosa" not in _tudo_que_o_banco_sabe(sessao)


def test_eliminar_nao_mexe_na_auditoria_dos_outros_clientes(client, sessao):
    ana, _, _ = _cliente_completo(client)
    bia = novo_cliente(client, nome="Carla Dias", telefone="41911112222")
    novo_obt(client, bia["id"])
    client.patch(f"/clientes/{bia['id']}", json={"grupo": "G"})
    antes = sessao.scalar(text("SELECT count(*) FROM auditoria WHERE cliente_id = :c"), {"c": bia["id"]})
    _excluir(client, ana)
    client.post(f"/auditoria/apagados/{ana['id']}/eliminar", json={"nome_confirmado": "Ana Souza", "motivo": "Teste"})
    sessao.expire_all()
    assert sessao.scalar(text("SELECT count(*) FROM auditoria WHERE cliente_id = :c"), {"c": bia["id"]}) == antes
    assert "Carla Dias" in _tudo_que_o_banco_sabe(sessao)


def test_eliminar_tira_a_citacao_do_cliente_eliminado_do_historico_de_outro_cliente(client, sessao):
    ana = novo_cliente(client, nome="Ana Souza")
    bia = novo_cliente(client, nome="Bia Souza")
    antigo = novo_obt(client, ana["id"])
    novo = novo_obt(client, bia["id"])
    sessao.execute(text("UPDATE processos SET processo_anterior_id = :a WHERE id = :n"),
                   {"a": antigo["id"], "n": novo["id"]})
    sessao.commit()
    _excluir(client, ana)
    client.post(f"/auditoria/apagados/{ana['id']}/eliminar", json={"nome_confirmado": "Ana Souza", "motivo": "Teste"})
    citacoes = sessao.scalar(text(
        "SELECT count(*) FROM auditoria WHERE (antes ->> 'processo_anterior_id') = :p "
        "OR (depois ->> 'processo_anterior_id') = :p"), {"p": str(antigo["id"])})
    assert citacoes == 0


def test_eliminar_exige_o_nome_certo_e_o_motivo(client, sessao):
    cliente = novo_cliente(client)
    client.delete(f"/clientes/{cliente['id']}")
    url = f"/auditoria/apagados/{cliente['id']}/eliminar"
    assert client.post(url, json={"nome_confirmado": "Outra Pessoa", "motivo": "Pedido do titular"}).status_code == 422
    assert client.post(url, json={"nome_confirmado": "Ana Souza", "motivo": "x"}).status_code == 422  # curto
    assert client.post(url, json={"nome_confirmado": "Ana Souza"}).status_code == 422  # sem motivo
    assert client.post(url, json={"nome_confirmado": "Ana Souza", "motivo": "Pedido do titular", "extra": 1}).status_code == 422
    assert client.get("/auditoria/apagados").json()  # nada foi eliminado


def test_so_elimina_quem_ja_foi_excluido(client):
    cliente = novo_cliente(client)
    resposta = client.post(f"/auditoria/apagados/{cliente['id']}/eliminar",
                           json={"nome_confirmado": "Ana Souza", "motivo": "Pedido do titular"})
    assert resposta.status_code == 409 and "está no sistema" in resposta.json()["detail"]
    assert client.get(f"/clientes/{cliente['id']}").status_code == 200


def test_eliminar_duas_vezes_da_404_na_segunda(client):
    cliente = novo_cliente(client)
    client.delete(f"/clientes/{cliente['id']}")
    dados = {"nome_confirmado": "Ana Souza", "motivo": "Pedido do titular"}
    assert client.post(f"/auditoria/apagados/{cliente['id']}/eliminar", json=dados).status_code == 200
    assert client.post(f"/auditoria/apagados/{cliente['id']}/eliminar", json=dados).status_code == 404


def test_a_funcao_do_banco_e_a_unica_porta_para_apagar_auditoria(client, sessao):
    # a exceção da guarda só vale dentro da função: DELETE e UPDATE comuns seguem recusados
    from sqlalchemy.exc import DBAPIError
    cliente = novo_cliente(client)
    client.delete(f"/clientes/{cliente['id']}")
    for comando in ("DELETE FROM auditoria", "UPDATE auditoria SET depois = NULL"):
        with pytest.raises(DBAPIError, match="não pode ser alterada"):
            sessao.execute(text(comando))
        sessao.rollback()
    # e a exceção não fica ligada depois da eliminação (a configuração vale só na transação)
    client.post(f"/auditoria/apagados/{cliente['id']}/eliminar", json={"nome_confirmado": "Ana Souza", "motivo": "Teste"})
    with pytest.raises(DBAPIError, match="não pode ser alterada"):
        sessao.execute(text("DELETE FROM auditoria"))
    sessao.rollback()


def test_eliminar_limpa_o_cache_de_respostas_de_criacao(client, sessao):
    # as respostas guardadas pela idempotência trazem dados do cliente por até 24 h
    cliente = client.post("/clientes", json={"nome": "Ana Souza", "telefone": "41999998888"},
                          headers={"Idempotency-Key": "chave-de-teste-0001"}).json()
    assert sessao.scalar(text("SELECT count(*) FROM chaves_idempotencia")) == 1
    client.delete(f"/clientes/{cliente['id']}")
    client.post(f"/auditoria/apagados/{cliente['id']}/eliminar", json={"nome_confirmado": "Ana Souza", "motivo": "Teste"})
    sessao.expire_all()
    assert sessao.scalar(text("SELECT count(*) FROM chaves_idempotencia")) == 0


# ---------------------------------------------------------------- só admin

ROTAS_ADMIN = [("GET", "/auditoria/apagados", None), ("POST", "/auditoria/apagados/1/restaurar", None),
               ("POST", "/auditoria/apagados/1/eliminar", {"nome_confirmado": "x", "motivo": "motivo longo"})]


@pytest.mark.parametrize("perfil", ["atendente", "leitor"])
@pytest.mark.parametrize("metodo,caminho,corpo", ROTAS_ADMIN)
def test_restaurar_listar_e_eliminar_so_admin(como, perfil, metodo, caminho, corpo):
    assert como(perfil).request(metodo, caminho, json=corpo).status_code == 403


@pytest.mark.parametrize("metodo,caminho,corpo", ROTAS_ADMIN)
def test_sem_login_401(client_anonimo, metodo, caminho, corpo):
    assert client_anonimo.request(metodo, caminho, json=corpo).status_code == 401
