from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.enums import Consulado, DocsREN, Orientacao, TipoEvento
from app.models import (Cliente, Evento, FormularioDS160, Perfil, Processo, ProcessoPASS, ProcessoREN,
                        Situacao, Solicitante)
from tests.conftest import novo_obt


def test_migration_carrega_perfis_e_situacoes(sessao):
    assert {p.nome for p in sessao.scalars(select(Perfil))} == {"admin", "atendente", "leitor"}
    assert sessao.get(Situacao, ("OBT", "Pago")) is not None
    assert sessao.get(Situacao, ("REN", "Pago")) is None  # Pago não existe para renovação


def test_heranca_consulta_pela_tabela_base_devolve_o_tipo_certo(sessao, cliente):
    sessao.add_all([novo_obt(cliente),
                    ProcessoREN(cliente_id=cliente.id, situacao="Cadastro", consulado=Consulado.RIO),
                    ProcessoPASS(cliente_id=cliente.id, situacao="Pendente")])
    sessao.commit()
    tipos = [(type(p).__name__, p.tipo) for p in sessao.scalars(select(Processo).order_by(Processo.id))]
    assert tipos == [("ProcessoOBT", "OBT"), ("ProcessoREN", "REN"), ("ProcessoPASS", "PASS")]


def test_data_despacho_e_calculada_pelo_banco(sessao, cliente):
    ren = ProcessoREN(cliente_id=cliente.id, situacao="Cadastro", consulado=Consulado.RIO,
                      data_casv=date(2026, 10, 16))
    sessao.add(ren)
    sessao.commit()
    sessao.refresh(ren)
    assert ren.data_despacho == date(2026, 10, 9)
    assert ren.docs == DocsREN.PENDENTE


def test_situacao_de_outro_tipo_e_recusada(sessao, cliente):
    sessao.add(novo_obt(cliente, situacao="Pix"))  # Pix só existe para passaporte
    with pytest.raises(IntegrityError):
        sessao.commit()


def test_um_so_titular_por_processo(sessao, cliente):
    processo = novo_obt(cliente)
    processo.solicitantes.append(Solicitante(nome="Outro", titular=True))
    sessao.add(processo)
    with pytest.raises(IntegrityError):
        sessao.commit()


def test_varios_solicitantes_sao_contados_nao_armazenados(sessao, cliente):
    processo = novo_obt(cliente)
    processo.solicitantes += [Solicitante(nome="Filho 1"), Solicitante(nome="Filho 2")]
    sessao.add(processo)
    sessao.commit()
    assert len(processo.solicitantes) == 3
    assert [s.titular for s in processo.solicitantes] == [True, False, False]


def test_resultado_e_por_solicitante(sessao, cliente):
    from app.enums import Resultado
    processo = novo_obt(cliente)
    processo.solicitantes.append(Solicitante(nome="Filho", resultado=Resultado.NEGADO))
    sessao.add(processo)
    sessao.commit()
    assert [s.resultado for s in processo.solicitantes] == [Resultado.PROCESSANDO, Resultado.NEGADO]


def test_agendada_exige_data(sessao, cliente):
    sessao.add(novo_obt(cliente, orientacao=Orientacao.AGENDADA))
    with pytest.raises(IntegrityError):
        sessao.commit()


def test_codigo_ds160_valida_formato_e_e_unico(sessao, cliente):
    processo = novo_obt(cliente)
    sessao.add(processo)
    sessao.commit()
    titular = processo.solicitantes[0]
    titular.formularios.append(FormularioDS160(codigo="AA00ABC123"))
    sessao.commit()

    sessao.add(FormularioDS160(solicitante_id=titular.id, codigo="AA00ABC123"))  # repetido
    with pytest.raises(IntegrityError):
        sessao.commit()
    sessao.rollback()

    sessao.add(FormularioDS160(solicitante_id=titular.id, codigo="XX00ABC123"))  # formato errado
    with pytest.raises(IntegrityError):
        sessao.commit()


def test_reabrir_exige_motivo(sessao, cliente):
    processo = novo_obt(cliente)
    sessao.add(processo)
    sessao.commit()
    sessao.add(Evento(processo_id=processo.id, tipo=TipoEvento.REABERTO,
                      situacao_anterior="Concluido", situacao_nova="Processando"))
    with pytest.raises(IntegrityError):
        sessao.commit()
    sessao.rollback()
    sessao.add(Evento(processo_id=processo.id, tipo=TipoEvento.REABERTO, motivo="Cliente tentará de novo",
                      situacao_anterior="Concluido", situacao_nova="Processando"))
    sessao.commit()


def test_nome_de_cliente_unico_sem_diferenciar_maiusculas(sessao, cliente):
    sessao.add(Cliente(nome="ANA SOUZA"))
    with pytest.raises(IntegrityError):
        sessao.commit()


def test_nova_tentativa_liga_ao_processo_anterior_do_mesmo_cliente(sessao, cliente):
    primeiro = novo_obt(cliente)
    sessao.add(primeiro)
    sessao.commit()
    segundo = novo_obt(cliente, processo_anterior_id=primeiro.id)  # mesmo cliente de novo: permitido
    sessao.add(segundo)
    sessao.commit()
    assert segundo.processo_anterior is primeiro
    assert len(cliente.processos) == 2


def test_apagar_processo_apaga_solicitantes_e_formularios(sessao, cliente):
    processo = novo_obt(cliente)
    processo.solicitantes[0].formularios.append(FormularioDS160(codigo="AA00ABC123"))
    sessao.add(processo)
    sessao.commit()
    sessao.delete(processo)
    sessao.commit()
    assert sessao.scalars(select(Solicitante)).all() == []
    assert sessao.scalars(select(FormularioDS160)).all() == []


def test_consulado_pode_ficar_vazio_sem_data_marcada(sessao, cliente):
    processo = novo_obt(cliente, consulado=None)
    sessao.add(processo)
    sessao.commit()
    assert processo.consulado is None


def test_banco_aceita_obt_com_data_e_sem_consulado_para_o_historico(sessao, cliente):
    # histórico importado (consulado N/D): o banco aceita; a regra "com data, consulado" vale na API
    processo = novo_obt(cliente, consulado=None, data_casv=date(2026, 12, 1))
    sessao.add(processo)
    sessao.commit()
    assert processo.consulado is None


def test_renovacao_exige_consulado_quando_ha_data_marcada(sessao, cliente):
    sessao.add(ProcessoREN(cliente_id=cliente.id, situacao="Cadastro", data_casv=date(2026, 12, 1)))
    with pytest.raises(IntegrityError):
        sessao.commit()


def test_processo_guarda_observacao_livre(sessao, cliente):
    processo = novo_obt(cliente, observacao="Corrigir endereço no DS-160")
    sessao.add(processo)
    sessao.commit()
    sessao.expire_all()
    assert sessao.get(Processo, processo.id).observacao == "Corrigir endereço no DS-160"
