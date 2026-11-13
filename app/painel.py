"""Mapeamento da view vw_painel_processos (somente leitura).

Fica fora do `Base.metadata` de propósito: o Alembic não deve tentar criar uma tabela chamada
vw_painel_processos; a view é criada por SQL na migration 0003.
"""
from sqlalchemy import Column, Date, DateTime, Integer, MetaData, String, Table

painel = Table(
    "vw_painel_processos", MetaData(),
    Column("processo_id", Integer), Column("tipo", String), Column("situacao", String),
    Column("cliente_id", Integer), Column("cliente", String), Column("telefone", String),
    Column("grupo", String), Column("titular", String), Column("n_solicitantes", Integer),
    Column("solicitantes", String), Column("resultado_geral", String), Column("n_formularios", Integer),
    Column("consulado", String), Column("data_casv", Date), Column("data_entrevista", Date),
    Column("data_despacho", Date), Column("data_pf", Date), Column("prazo_pf", Date),
    Column("codigo_rastreio", String), Column("atualizado_em", DateTime(timezone=True)),
    Column("orientacao", String), Column("orientacao_data", Date), Column("orientacao_por", String),
    Column("despachado_em", Date), Column("previsao_orientacao", Date),
    Column("ds160_status", String), Column("ds160_fechados", Integer),
)
