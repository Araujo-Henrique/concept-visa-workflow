"""O seed fictício: gera dados que respeitam as regras da aplicação e nunca se mistura com dados reais."""
import random
import re
from datetime import date

import pytest
from sqlalchemy import func, select

from app.models import Cliente, Evento, FormularioDS160, Processo, Solicitante, Usuario
from app.seed import gerar_nomes, semear
from tests.conftest import SENHA_TESTE

HOJE = date(2026, 11, 6)


@pytest.fixture
def resumo(sessao):
    resultado = semear(sessao, SENHA_TESTE, quantidade=24, hoje=HOJE)
    sessao.commit()
    return resultado


def test_cria_o_volume_esperado_com_os_tres_tipos(sessao, resumo):
    assert resumo["clientes"] == 24
    assert resumo["usuarios"] == 4
    assert resumo["processos"] >= 24  # ao menos um por cliente
    tipos = set(sessao.scalars(select(Processo.tipo)))
    assert tipos == {"OBT", "REN", "PASS"}
    assert resumo["eventos"] >= resumo["processos"]  # cada processo tem ao menos o "criado"


def test_tudo_e_ficticio_sem_e_mail_real(sessao, resumo):
    emails = [e for e in sessao.scalars(select(Cliente.email)) if e] + list(sessao.scalars(select(Usuario.email)))
    assert emails and all(e.endswith("@exemplo.com") for e in emails)


def test_cada_processo_tem_exatamente_um_titular_e_o_historico_coerente(sessao, resumo):
    for processo in sessao.scalars(select(Processo)):
        assert sum(s.titular for s in processo.solicitantes) == 1
        eventos = processo.eventos
        assert eventos[0].tipo == "criado"
        # a cadeia do histórico fecha: cada "situação anterior" é a "nova" do evento anterior
        for antes, depois in zip(eventos, eventos[1:]):
            assert depois.situacao_anterior == antes.situacao_nova
        assert eventos[-1].situacao_nova == processo.situacao


def test_regras_entre_campos_valem_nos_dados_gerados(sessao, resumo):
    for processo in sessao.scalars(select(Processo)):
        if processo.tipo in ("OBT", "REN") and processo.data_casv:
            assert processo.consulado is not None  # data de CASV sempre vem com consulado
    ren = [p for p in sessao.scalars(select(Processo).where(Processo.tipo == "REN")) if p.data_casv]
    assert ren and all(p.data_despacho == p.data_casv.fromordinal(p.data_casv.toordinal() - 7) for p in ren)


def test_codigos_ds160_seguem_o_padrao_e_nao_se_repetem(sessao, resumo):
    codigos = list(sessao.scalars(select(FormularioDS160.codigo)))
    assert codigos and len(codigos) == len(set(codigos))
    assert all(re.fullmatch(r"AA00[A-Z0-9]{6}", c) for c in codigos)


def test_cenarios_de_demonstracao_estao_presentes(sessao, resumo):
    # nova tentativa depois de uma negativa
    retentativa = sessao.scalars(select(Processo).where(Processo.processo_anterior_id.is_not(None))).all()
    assert retentativa
    anterior = sessao.get(Processo, retentativa[0].processo_anterior_id)
    assert anterior.cliente_id == retentativa[0].cliente_id
    assert all(s.resultado == "Negado" for s in anterior.solicitantes)
    # processo reaberto com motivo
    reabertos = sessao.scalars(select(Evento).where(Evento.tipo == "reaberto")).all()
    assert reabertos and all(e.motivo for e in reabertos)
    # famílias (clientes do mesmo grupo)
    assert sessao.scalar(select(func.count(func.distinct(Cliente.grupo)))) >= 4


def test_so_o_admin_demo_entra_com_senha_os_outros_so_com_o_google(sessao, resumo, client_anonimo):
    def entrar(email):
        return client_anonimo.post("/auth/login", json={"email": email, "senha": SENHA_TESTE}).status_code

    assert entrar("admin@exemplo.com") == 200
    assert [entrar(e) for e in ("atendente@exemplo.com", "leitor@exemplo.com", "ex-funcionario@exemplo.com")] == [401] * 3


def test_o_painel_mostra_os_dados_semeados(sessao, resumo, client_anonimo):
    token = client_anonimo.post("/auth/login", json={"email": "admin@exemplo.com", "senha": SENHA_TESTE}).json()
    cabecalho = {"Authorization": f"Bearer {token['access_token']}"}
    painel = client_anonimo.get("/painel", params={"limit": 200}, headers=cabecalho)
    assert painel.status_code == 200
    assert len(painel.json()) == int(painel.headers["X-Total-Count"]) == resumo["processos"]
    agenda = client_anonimo.get("/painel/agenda", params={"de": "2026-09-01", "ate": "2026-12-01"},
                                headers=cabecalho)
    assert agenda.status_code == 200 and agenda.json()  # há datas marcadas à vista


def test_recusa_banco_que_ja_tem_clientes(sessao, resumo):
    with pytest.raises(RuntimeError, match="já tem clientes"):
        semear(sessao, SENHA_TESTE, quantidade=5, hoje=HOJE)
    assert sessao.scalar(select(func.count()).select_from(Cliente)) == resumo["clientes"]  # nada foi acrescentado


def test_nao_se_mistura_com_cliente_real_ja_existente(sessao):
    sessao.add(Cliente(nome="Cliente Real Qualquer"))
    sessao.commit()
    with pytest.raises(RuntimeError):
        semear(sessao, SENHA_TESTE, quantidade=5, hoje=HOJE)


def test_mesma_semente_gera_os_mesmos_nomes():
    assert gerar_nomes(random.Random(42), 12) == gerar_nomes(random.Random(42), 12)
    assert gerar_nomes(random.Random(42), 12) != gerar_nomes(random.Random(7), 12)
    nomes = gerar_nomes(random.Random(1), 50)
    assert len(nomes) == len({n.lower() for n in nomes})  # nunca repete (o nome do cliente é único)


def test_sem_senha_os_usuarios_demo_nao_entram_por_senha(sessao):
    semear(sessao, None, quantidade=4, hoje=HOJE)
    sessao.commit()
    assert all(u.senha_hash is None for u in sessao.scalars(select(Usuario)))
    assert sessao.scalar(select(func.count()).select_from(Solicitante)) > 0
