"""Importação do banco do Projeto 1. A "origem" é um banco antigo fictício, criado no esquema `origem`
do banco de teste (o importador lê com search_path=origem), com os casos reais que o levantamento achou."""
import os
from datetime import date

import psycopg
import pytest
from psycopg.rows import dict_row
from sqlalchemy import select

from app.importacao.projeto1 import chave, importar, ler_codigos
from app.models import (Cliente, Evento, FormularioDS160, Processo, ProcessoOBT, ProcessoREN, Solicitante, Usuario)

DDL = """
DROP SCHEMA IF EXISTS origem CASCADE;
CREATE SCHEMA origem;
SET search_path = origem;
CREATE TABLE funcionarios (id serial PRIMARY KEY, nome text, ativo boolean DEFAULT true);
CREATE TABLE clientes (id serial PRIMARY KEY, nome text, email text, telefone text, grupo text);
CREATE TABLE processos_obt (
    id serial PRIMARY KEY, cliente_id int, consulado text, n_solicitantes int DEFAULT 1,
    monitoramento text DEFAULT 'Ativo', data_casv date, data_entrevista date, data_vencimento_taxa date,
    status_rascunho text DEFAULT 'Pendente', status_ds text DEFAULT 'Pendente', orientacao text DEFAULT 'Pendente',
    orientacao_data date, orientacao_por_id int, situacao text, {ds160} codigo_rastreio text,
    resultado text DEFAULT 'Processando');
CREATE TABLE processos_ren (
    id serial PRIMARY KEY, cliente_id int, consulado text, n_solicitantes int DEFAULT 1, data_casv date,
    docs text DEFAULT 'Pendente', status_rascunho text DEFAULT 'Pendente', status_ds text DEFAULT 'Pendente',
    situacao text, {ds160} codigo_rastreio text, endereco text);
CREATE TABLE passaportes (id serial PRIMARY KEY, cliente_id int, n_solicitantes int DEFAULT 1,
    data_pf date, prazo_pf date, situacao text);
"""
DS160 = "codigo_ds160 text, notas_ds160 text,"


def inserir(conn, tabela, **campos):
    colunas = ", ".join(campos)
    conn.execute(f"INSERT INTO {tabela} ({colunas}) VALUES ({', '.join(['%s'] * len(campos))})", list(campos.values()))


def criar_origem(conn, com_ds160=True):
    conn.execute(DDL.format(ds160=DS160 if com_ds160 else ""))
    inserir(conn, "funcionarios", nome="Gabriel Vieira", ativo=True)
    inserir(conn, "funcionarios", nome="Roger Cardoso", ativo=False)
    for nome, tel in (("Ana Souza", "41999990001"), ("Bia Lima", "41999990002"), ("Carlos Dias", "41999990003")):
        inserir(conn, "clientes", nome=nome, telefone=tel)

    obt1 = dict(cliente_id=1, consulado="SP", n_solicitantes=3, situacao="Concluido", status_ds="Revisado",
                resultado="Aprovado", orientacao="Agendada", orientacao_data=date(2026, 5, 1), orientacao_por_id=1,
                data_casv=date(2026, 6, 1), status_rascunho="Enviado")
    obt2 = dict(cliente_id=2, consulado="N/D", n_solicitantes=1, situacao="Pago", status_ds="Preenchido",
                data_casv=date(2025, 3, 3), orientacao_por_id=2)  # N/D com data; funcionário fora do CSV
    obt3 = dict(cliente_id=3, consulado="RIO", n_solicitantes=1, situacao="Processando")
    if com_ds160:
        obt1.update(codigo_ds160="AA00AAAAAA - Ana\nAA00AAAAAB - novo\nAA00AAAAAC - Pedro\nAA00AAAAAD - Maria",
                    notas_ds160="corrigir endereco")
        obt3.update(codigo_ds160="AA00AAAAAA - Carlos")  # código repetido do processo 1
    for r in (obt1, obt2, obt3):
        inserir(conn, "processos_obt", **r)

    ren = dict(cliente_id=1, consulado="RIO", n_solicitantes=1, situacao="Cadastro", status_rascunho="Enviado",
               status_ds="Fechado", data_casv=date(2026, 10, 16), endereco="Rua A, 1")
    if com_ds160:
        ren.update(codigo_ds160="AA00BBBBBB - Ana\nlinha solta sem padrao")
    inserir(conn, "processos_ren", **ren)
    inserir(conn, "passaportes", cliente_id=2, n_solicitantes=2, situacao=None, data_pf=date(2026, 11, 20))


@pytest.fixture
def origem(engine, sessao):
    url = os.environ["TEST_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, autocommit=True, options="-c search_path=origem", row_factory=dict_row) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS origem")
        yield conn
        conn.execute("DROP SCHEMA IF EXISTS origem CASCADE")


CSV = {"gabriel vieira": ("gabriel@empresa.com.br", "admin")}  # Roger não está no CSV


# ---------------------------------------------------------------- funções puras

def test_chave_ignora_acento_e_caixa():
    assert chave("José Silva") == chave("jose") == "jose"


def test_ler_codigos_separa_pessoas_e_formularios_refeitos():
    texto = "AA00AAAAAA - Ana\nAA00AAAAAB - novo\n\nAA00AAAAAC - Pedro Alves\nAA00AAAAAD - novo\nanotacao qualquer"
    codigos, fora = ler_codigos(texto)
    assert codigos == [("AA00AAAAAA", "Ana"), ("AA00AAAAAB", "Ana"), ("AA00AAAAAC", "Pedro"), ("AA00AAAAAD", "Pedro")]
    assert fora == ["anotacao qualquer"]


def test_ler_codigos_aceita_minusculas_e_codigo_sem_nome():
    assert ler_codigos("aa00abcdef") == ([("AA00ABCDEF", None)], [])
    assert ler_codigos(None) == ([], [])


# ---------------------------------------------------------------- importação

def test_importa_tudo_e_a_conferencia_bate(origem, sessao):
    criar_origem(origem)
    rel = importar(origem, sessao, CSV)
    assert rel.confere()
    assert rel.origem["clientes"] == rel.destino["clientes"] == 3
    assert rel.destino["processos_obt"] == 3 and rel.destino["processos_ren"] == 1 and rel.destino["passaportes"] == 1
    assert rel.origem["solicitantes (esperados)"] == rel.destino["solicitantes (esperados)"] == 3 + 1 + 1 + 1 + 2


def test_solicitantes_formularios_e_resultado_do_processo_com_varias_pessoas(origem, sessao):
    criar_origem(origem)
    importar(origem, sessao, CSV)
    ana = sessao.scalars(select(Cliente).where(Cliente.nome == "Ana Souza")).one()
    obt = sessao.scalars(select(ProcessoOBT).where(ProcessoOBT.cliente_id == ana.id)).one()

    assert [(s.nome, s.titular) for s in obt.solicitantes] == [("Ana Souza", True), ("Pedro", False), ("Maria", False)]
    assert {s.resultado.value for s in obt.solicitantes} == {"Aprovado"}
    codigos = {s.nome: [f.codigo for f in s.formularios] for s in obt.solicitantes}
    assert codigos == {"Ana Souza": ["AA00AAAAAA", "AA00AAAAAB"], "Pedro": ["AA00AAAAAC"], "Maria": ["AA00AAAAAD"]}
    assert {f.status.value for s in obt.solicitantes for f in s.formularios} == {"Revisado"}
    assert obt.observacao == "corrigir endereco"


def test_consulado_nd_com_data_entra_com_consulado_vazio(origem, sessao):
    criar_origem(origem)
    importar(origem, sessao, CSV)
    bia = sessao.scalars(select(Cliente).where(Cliente.nome == "Bia Lima")).one()
    obt = sessao.scalars(select(ProcessoOBT).where(ProcessoOBT.cliente_id == bia.id)).one()
    assert obt.consulado is None and obt.data_casv == date(2025, 3, 3)


def test_status_ds_sem_formulario_nao_se_perde(origem, sessao):
    criar_origem(origem)
    importar(origem, sessao, CSV)
    bia = sessao.scalars(select(Cliente).where(Cliente.nome == "Bia Lima")).one()
    obt = sessao.scalars(select(ProcessoOBT).where(ProcessoOBT.cliente_id == bia.id)).one()
    assert obt.observacao == "Status DS-160 (histórico): Preenchido"


def test_codigo_repetido_em_outro_processo_e_ignorado_com_aviso(origem, sessao):
    criar_origem(origem)
    rel = importar(origem, sessao, CSV)
    assert sessao.scalars(select(FormularioDS160).where(FormularioDS160.codigo == "AA00AAAAAA")).one()
    assert any("AA00AAAAAA repetido" in a for a in rel.avisos)
    assert rel.origem["formularios ds160 (linhas de código)"] == 6  # 4 + 1 duplicado + 1 da renovação
    assert rel.destino["formularios ds160 (linhas de código)"] == 5


def test_linha_fora_do_padrao_vai_para_a_observacao(origem, sessao):
    criar_origem(origem)
    importar(origem, sessao, CSV)
    ren = sessao.scalars(select(ProcessoREN)).one()
    assert ren.observacao == "linha solta sem padrao"
    assert ren.status_rascunho.value == "Enviado"
    sessao.refresh(ren)  # data_despacho é gerada pelo banco: só aparece depois de gravar e reler
    assert ren.data_despacho == date(2026, 10, 9)


def test_usuarios_so_dos_funcionarios_no_csv_e_orientacao_mapeada(origem, sessao):
    criar_origem(origem)
    rel = importar(origem, sessao, CSV)
    usuarios = sessao.scalars(select(Usuario)).all()
    assert [(u.nome, u.email, u.perfil.nome, u.ativo, u.senha_hash) for u in usuarios] == [
        ("Gabriel Vieira", "gabriel@empresa.com.br", "admin", True, None)]
    por_cliente = {p.cliente.nome: p.orientacao_por_id for p in sessao.scalars(select(ProcessoOBT))}
    assert por_cliente["Ana Souza"] == usuarios[0].id
    assert por_cliente["Bia Lima"] is None  # Roger não está no CSV
    assert any("sem usuário" in a and "Roger Cardoso (1)" in a for a in rel.avisos)  # o aviso diz quem faltou


def test_funcionario_inativo_no_csv_vira_usuario_sem_acesso_e_preserva_o_historico(origem, sessao):
    criar_origem(origem)
    csv_completo = {**CSV, "roger cardoso": ("roger@empresa.com.br", "leitor")}
    rel = importar(origem, sessao, csv_completo)
    roger = sessao.scalars(select(Usuario).where(Usuario.nome == "Roger Cardoso")).one()
    assert roger.ativo is False and roger.perfil.nome == "leitor"  # existe, mas não pode entrar
    bia = sessao.scalars(select(Cliente).where(Cliente.nome == "Bia Lima")).one()
    obt = sessao.scalars(select(ProcessoOBT).where(ProcessoOBT.cliente_id == bia.id)).one()
    assert obt.orientacao_por_id == roger.id  # a orientação continua atribuída a quem a deu
    assert not any("sem usuário" in a for a in rel.avisos)


def test_passaporte_sem_situacao_vira_pendente(origem, sessao):
    criar_origem(origem)
    rel = importar(origem, sessao, CSV)
    pas = sessao.scalars(select(Processo).where(Processo.tipo == "PASS")).one()
    assert pas.situacao == "Pendente" and len(pas.solicitantes) == 2
    assert any("PASS 1" in a for a in rel.avisos)


def test_cada_processo_ganha_evento_criado(origem, sessao):
    criar_origem(origem)
    importar(origem, sessao, CSV)
    sessao.flush()
    eventos = sessao.scalars(select(Evento)).all()
    assert len(eventos) == 5 and {e.tipo.value for e in eventos} == {"criado"}


def test_funciona_com_banco_antigo_sem_colunas_do_ds160(origem, sessao):
    criar_origem(origem, com_ds160=False)
    rel = importar(origem, sessao, CSV)
    assert rel.confere()
    assert sessao.scalars(select(FormularioDS160)).all() == []
    assert rel.destino["formularios ds160 (linhas de código)"] == 0


def test_importacao_funciona_sem_csv_de_usuarios(origem, sessao):
    criar_origem(origem)
    rel = importar(origem, sessao)
    assert rel.confere() and sessao.scalars(select(Usuario)).all() == []


def test_recusa_banco_de_destino_com_dados(origem, sessao):
    criar_origem(origem)
    sessao.add(Cliente(nome="Já existia"))
    sessao.commit()
    with pytest.raises(RuntimeError, match="já tem dados"):
        importar(origem, sessao, CSV)


def test_rollback_desfaz_tudo(origem, sessao):
    criar_origem(origem)
    importar(origem, sessao, CSV)
    sessao.rollback()  # é o que a simulação faz
    assert sessao.scalars(select(Cliente)).all() == [] and sessao.scalars(select(Solicitante)).all() == []
