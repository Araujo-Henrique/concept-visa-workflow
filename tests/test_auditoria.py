"""Auditoria: toda mudança em clientes, processos, pessoas e DS-160 fica registrada pelo banco, com antes e
depois, quem fez e de onde veio. O rastro sobrevive à remoção e não pode ser alterado.
"""
import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError

from app import auditoria as modulo_auditoria
from app.models import Auditoria, Cliente
from tests.test_api import novo_cliente, novo_obt
from tests.test_autorizacao import como  # noqa: F401  (fixture)


def _linhas(sessao, **filtros):
    sessao.expire_all()
    consulta = select(Auditoria).order_by(Auditoria.id)
    for campo, valor in filtros.items():
        consulta = consulta.where(getattr(Auditoria, campo) == valor)
    return list(sessao.scalars(consulta))


def _processo_completo(client):
    """Cliente + processo OBT com uma pessoa extra e um DS-160, tudo pela API."""
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"], solicitantes_extras=["Bia Souza"])
    titular = next(s for s in processo["solicitantes"] if s["titular"])
    resposta = client.post(f"/solicitantes/{titular['id']}/formularios-ds160", json={"codigo": "AA00ABC123"})
    assert resposta.status_code == 201, resposta.text
    return cliente, processo


# ---------------------------------------------------------------- o que é gravado

def test_criar_pela_api_grava_o_registro_inteiro_com_quem_e_o_codigo_da_requisicao(client, sessao, usuario_teste):
    resposta = client.post("/clientes", json={"nome": "Ana Souza", "telefone": "41999998888"})
    [linha] = _linhas(sessao, tabela="clientes")
    assert (linha.acao, linha.registro_id, linha.cliente_id) == ("criou", resposta.json()["id"], resposta.json()["id"])
    assert linha.antes is None
    assert linha.depois["nome"] == "Ana Souza" and linha.depois["telefone"] == "41999998888"
    assert linha.usuario_id == usuario_teste.id and linha.origem == "api"
    assert linha.requisicao == resposta.headers["X-Request-ID"]  # liga a auditoria à linha do log


def test_editar_grava_so_os_campos_que_mudaram(client, sessao):
    cliente = novo_cliente(client, telefone="41999998888")
    client.patch(f"/clientes/{cliente['id']}", json={"grupo": "Família Souza", "telefone": "41999998888"})
    linha = _linhas(sessao, tabela="clientes", acao="editou")[-1]
    # o telefone foi enviado igual: não mudou, não aparece
    assert linha.antes == {"grupo": None} and linha.depois == {"grupo": "Família Souza"}


def test_edicao_que_nao_muda_nada_nao_gera_linha(client, sessao):
    cliente = novo_cliente(client, grupo="A")
    client.patch(f"/clientes/{cliente['id']}", json={"grupo": "A"})
    assert _linhas(sessao, tabela="clientes", acao="editou") == []


def test_update_no_banco_que_nao_muda_nada_nao_gera_linha(sessao, cliente):
    # o teste acima nem chega ao banco (o SQLAlchemy não manda UPDATE sem mudança); este manda direto
    sessao.execute(text("UPDATE clientes SET grupo = grupo, nome = nome"))
    sessao.commit()
    assert _linhas(sessao, acao="editou") == []


def test_atualizado_em_nao_e_tratado_como_alteracao(client, sessao):
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"])
    client.patch(f"/processos-obt/{processo['id']}", json={"observacao": "ligar amanhã"})
    linha = _linhas(sessao, tabela="processos", acao="editou")[-1]
    assert set(linha.depois) == {"observacao"}


def test_detalhe_do_processo_sabe_a_que_processo_e_cliente_pertence(client, sessao):
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"])
    client.patch(f"/processos-obt/{processo['id']}", json={"codigo_rastreio": "BR123"})
    linha = _linhas(sessao, tabela="processo_obt", acao="editou")[-1]
    assert (linha.processo_id, linha.cliente_id) == (processo["id"], cliente["id"])
    assert linha.antes == {"codigo_rastreio": None} and linha.depois == {"codigo_rastreio": "BR123"}


def test_mudar_situacao_fica_na_auditoria_do_processo(client, sessao):
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"])
    client.post(f"/processos/{processo['id']}/situacao", json={"situacao": "Pago"})
    linha = _linhas(sessao, tabela="processos", acao="editou")[-1]
    assert linha.antes == {"situacao": "Processando"} and linha.depois == {"situacao": "Pago"}


def test_ds160_sabe_o_processo_e_o_cliente(client, sessao):
    cliente, processo = _processo_completo(client)
    [linha] = _linhas(sessao, tabela="formularios_ds160")
    assert (linha.processo_id, linha.cliente_id) == (processo["id"], cliente["id"])


# ---------------------------------------------------------------- remoção: o rastro sobrevive

def test_apagar_cliente_com_processos_registra_tudo_numa_transacao_so(client, sessao):
    cliente, processo = _processo_completo(client)
    assert client.delete(f"/clientes/{cliente['id']}", params={"com_processos": True}).status_code == 204

    apagadas = _linhas(sessao, acao="apagou")
    assert {linha.tabela for linha in apagadas} == {
        "clientes", "processos", "processo_obt", "solicitantes", "formularios_ds160"}
    assert len({linha.transacao for linha in apagadas}) == 1  # uma operação: dá para mostrar como uma só
    assert all(linha.cliente_id == cliente["id"] for linha in apagadas)
    do_cliente = next(linha for linha in apagadas if linha.tabela == "clientes")
    assert do_cliente.antes["nome"] == "Ana Souza" and do_cliente.depois is None  # o registro inteiro


def test_historico_de_cliente_apagado_continua_legivel_pela_api(client, sessao):
    cliente, _ = _processo_completo(client)
    client.delete(f"/clientes/{cliente['id']}", params={"com_processos": True})
    resposta = client.get("/auditoria", params={"cliente_id": cliente["id"]})
    assert resposta.status_code == 200  # não é 404: o cliente não existe mais, o histórico sim
    acoes = {(a["tabela"], a["acao"]) for a in resposta.json()}
    assert ("clientes", "criou") in acoes and ("clientes", "apagou") in acoes
    assert ("formularios_ds160", "apagou") in acoes


def test_outra_tentativa_que_perde_a_referencia_tambem_e_registrada(client, sessao):
    # o DELETE de cliente limpa processo_anterior_id de processos de OUTROS clientes num UPDATE em massa:
    # uma auditoria feita só no Python não veria isso; o trigger vê
    ana = novo_cliente(client, nome="Ana Souza")
    bia = novo_cliente(client, nome="Bia Souza")
    antigo = novo_obt(client, ana["id"])
    novo = novo_obt(client, bia["id"])
    sessao.execute(text("UPDATE processos SET processo_anterior_id = :a WHERE id = :n"),
                   {"a": antigo["id"], "n": novo["id"]})
    sessao.commit()
    client.delete(f"/clientes/{ana['id']}", params={"com_processos": True})
    linha = _linhas(sessao, tabela="processos", registro_id=novo["id"], acao="editou")[-1]
    assert linha.antes == {"processo_anterior_id": antigo["id"]} and linha.depois == {"processo_anterior_id": None}
    assert linha.origem == "api"


def test_cascata_feita_pelo_proprio_banco_tambem_e_registrada(client, sessao):
    # alguém apaga direto no banco (psql): a cascata das FKs remove pessoas e DS-160 sem passar pela API
    cliente, processo = _processo_completo(client)
    sessao.execute(text("DELETE FROM eventos WHERE processo_id = :p"), {"p": processo["id"]})
    sessao.execute(text("DELETE FROM processos WHERE id = :p"), {"p": processo["id"]})
    sessao.commit()
    apagadas = {linha.tabela: linha for linha in _linhas(sessao, acao="apagou")}
    assert set(apagadas) == {"processos", "processo_obt", "solicitantes", "formularios_ds160"}
    # mesmo com o pai já apagado, cada linha sabe de que processo e cliente era
    assert all(linha.processo_id == processo["id"] for linha in apagadas.values())
    assert all(linha.cliente_id == cliente["id"] for linha in apagadas.values())
    assert all(linha.origem == "banco" and linha.usuario_id is None for linha in apagadas.values())


# ---------------------------------------------------------------- origem e isolamento

def test_edicao_manual_fora_da_api_fica_marcada_como_banco_e_sem_usuario(sessao, cliente):
    sessao.execute(update(Cliente).where(Cliente.id == cliente.id).values(grupo="mexido no psql"))
    sessao.commit()
    linha = _linhas(sessao, tabela="clientes", acao="editou")[-1]
    assert linha.origem == "banco" and linha.usuario_id is None and linha.requisicao is None


def test_o_usuario_nao_vaza_para_a_proxima_transacao_na_mesma_conexao(client, sessao, cliente):
    # a API marcou "usuário X" na conexão; o set_config é local à transação, então quem pega a conexão do pool
    # depois (aqui, a sessão do teste) não herda o usuário de ninguém
    client.patch(f"/clientes/{cliente.id}", json={"grupo": "pela api"})
    sessao.execute(update(Cliente).where(Cliente.id == cliente.id).values(grupo="fora da api"))
    sessao.commit()
    ultima = _linhas(sessao, tabela="clientes", acao="editou")[-1]
    assert ultima.depois == {"grupo": "fora da api"} and ultima.usuario_id is None and ultima.origem == "banco"


def test_depois_do_commit_a_proxima_transacao_continua_identificada(sessao, usuario_teste):
    modulo_auditoria.identificar(sessao, usuario_id=usuario_teste.id, origem="api")
    sessao.add(Cliente(nome="Primeira"))
    sessao.commit()
    sessao.add(Cliente(nome="Segunda"))  # nova transação
    sessao.commit()
    assert [linha.usuario_id for linha in _linhas(sessao, tabela="clientes")] == [usuario_teste.id] * 2


def test_seed_fica_marcado_como_seed(sessao):
    from app.seed import semear
    semear(sessao, None, quantidade=2)
    sessao.commit()
    origens = {linha.origem for linha in _linhas(sessao)}
    assert origens == {"seed"}


# ---------------------------------------------------------------- a auditoria não pode ser adulterada

@pytest.mark.parametrize("comando", ["UPDATE auditoria SET usuario_id = 999", "DELETE FROM auditoria"])
def test_auditoria_so_aceita_acrescentar(client, sessao, comando):
    novo_cliente(client)
    with pytest.raises(DBAPIError, match="não pode ser alterada"):
        sessao.execute(text(comando))
    sessao.rollback()
    assert len(_linhas(sessao)) == 1


# ---------------------------------------------------------------- leitura (só admin)

@pytest.mark.parametrize("perfil", ["atendente", "leitor"])
def test_so_admin_le_a_auditoria(como, perfil):
    assert como(perfil).get("/auditoria").status_code == 403


def test_sem_login_401(client_anonimo):
    assert client_anonimo.get("/auditoria").status_code == 401


def test_leitura_traz_o_nome_de_quem_fez_mais_nova_primeiro_e_o_total(client, usuario_teste):
    a = novo_cliente(client, nome="Ana Souza")
    client.patch(f"/clientes/{a['id']}", json={"grupo": "G1"})
    client.patch(f"/clientes/{a['id']}", json={"grupo": "G2"})
    resposta = client.get("/auditoria", params={"cliente_id": a["id"], "limit": 2})
    assert resposta.headers["X-Total-Count"] == "3"
    corpo = resposta.json()
    assert [linha["depois"] for linha in corpo] == [{"grupo": "G2"}, {"grupo": "G1"}]
    assert corpo[0]["usuario_nome"] == usuario_teste.nome


def test_filtro_por_processo_traz_processo_pessoas_e_ds160_mas_nao_o_cadastro_do_cliente(client):
    _, processo = _processo_completo(client)
    tabelas = {linha["tabela"] for linha in client.get("/auditoria", params={"processo_id": processo["id"]}).json()}
    assert tabelas == {"processos", "processo_obt", "solicitantes", "formularios_ds160"}


def test_filtro_de_clientes_apagados(client):
    a = novo_cliente(client, nome="Ana Souza")
    novo_cliente(client, nome="Bia Souza")
    client.delete(f"/clientes/{a['id']}")
    corpo = client.get("/auditoria", params={"tabela": "clientes", "acao": "apagou"}).json()
    assert [linha["antes"]["nome"] for linha in corpo] == ["Ana Souza"]


def test_filtro_com_valor_desconhecido_e_recusado(client):
    assert client.get("/auditoria", params={"tabela": "usuarios"}).status_code == 422
    assert client.get("/auditoria", params={"acao": "sumiu"}).status_code == 422
