"""OBT: previsao_orientacao (CASV - 14 dias, calculada pelo banco) e a coluna no painel

A orientação para a entrevista costuma acontecer 2 semanas antes do CASV. Assim como o prazo do despacho da
renovação (CASV - 7), a previsão é uma coluna GERADA pelo próprio banco: nunca fica desatualizada e ninguém a
digita. Ela é só uma previsão: NÃO muda o status da orientação (Pendente continua Pendente até alguém agendar).

Revision ID: 0014
Revises: 0013
"""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

# Mesma view da 0007 + previsao_orientacao no FINAL (CREATE OR REPLACE VIEW só acrescenta colunas ao fim).
VIEW = """
CREATE OR REPLACE VIEW vw_painel_processos AS
SELECT
    p.id                                                        AS processo_id,
    p.tipo,
    p.situacao,
    c.id                                                        AS cliente_id,
    c.nome                                                      AS cliente,
    c.telefone,
    c.grupo,
    max(s.nome) FILTER (WHERE s.titular)                        AS titular,
    count(s.id)                                                 AS n_solicitantes,
    coalesce(string_agg(s.nome, ', ' ORDER BY s.titular DESC, s.id), '') AS solicitantes,
    CASE
        WHEN bool_or(s.resultado = 'Processando') THEN 'Processando'
        WHEN bool_and(s.resultado = 'Aprovado')   THEN 'Aprovado'
        WHEN bool_and(s.resultado = 'Negado')     THEN 'Negado'
        ELSE 'Parcial'
    END                                                         AS resultado_geral,
    coalesce(max(f.total), 0)                                   AS n_formularios,
    coalesce(o.consulado, r.consulado)                          AS consulado,
    coalesce(o.data_casv, r.data_casv)                          AS data_casv,
    o.data_entrevista,
    r.data_despacho,
    pa.data_pf,
    pa.prazo_pf,
    coalesce(o.codigo_rastreio, r.codigo_rastreio)              AS codigo_rastreio,
    p.atualizado_em,
    o.orientacao,
    o.orientacao_data,
    u.nome                                                      AS orientacao_por,
    r.despachado_em,
    o.previsao_orientacao
FROM processos p
JOIN clientes c            ON c.id = p.cliente_id
LEFT JOIN processo_obt  o  ON o.processo_id  = p.id
LEFT JOIN processo_ren  r  ON r.processo_id  = p.id
LEFT JOIN processo_pass pa ON pa.processo_id = p.id
LEFT JOIN usuarios      u  ON u.id = o.orientacao_por_id
LEFT JOIN solicitantes  s  ON s.processo_id  = p.id
LEFT JOIN (
    SELECT s2.processo_id, count(*) AS total
    FROM formularios_ds160 fd
    JOIN solicitantes s2 ON s2.id = fd.solicitante_id
    GROUP BY s2.processo_id
) f ON f.processo_id = p.id
GROUP BY p.id, c.id, o.processo_id, r.processo_id, pa.processo_id, u.id
"""


def upgrade() -> None:
    op.add_column("processo_obt", sa.Column(
        "previsao_orientacao", sa.Date(), sa.Computed("data_casv - 14", persisted=True), nullable=True))
    op.execute(VIEW)


def downgrade() -> None:
    caminho = Path(__file__).with_name("0007_despachado_em.py")
    spec = importlib.util.spec_from_file_location("migration_0007", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    op.execute("DROP VIEW vw_painel_processos")
    op.execute(modulo.VIEW)
    op.drop_column("processo_obt", "previsao_orientacao")
