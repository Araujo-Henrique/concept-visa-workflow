"""REN: despachado_em (quando foi despachado de verdade) e a coluna no painel

Revision ID: 0007
Revises: 0006
"""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# Mesma view da 0005 + despachado_em no FINAL (CREATE OR REPLACE VIEW só acrescenta colunas ao fim).
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
    r.despachado_em
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

# Histórico: um REN concluído já foi despachado. A data real não existe no histórico; usa-se o prazo
# calculado (CASV - 7) e, sem CASV, o dia da última atualização do processo.
MARCAR_CONCLUIDOS = """
UPDATE processo_ren r
SET despachado_em = coalesce(r.data_despacho, p.atualizado_em::date)
FROM processos p
WHERE p.id = r.processo_id AND p.situacao = 'Concluido' AND r.despachado_em IS NULL
"""


def upgrade() -> None:
    op.add_column("processo_ren", sa.Column("despachado_em", sa.Date(), nullable=True))
    op.execute(MARCAR_CONCLUIDOS)
    op.execute(VIEW)


def downgrade() -> None:
    caminho = Path(__file__).with_name("0005_orientacao_no_painel.py")
    spec = importlib.util.spec_from_file_location("migration_0005", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    op.execute("DROP VIEW vw_painel_processos")
    op.execute(modulo.VIEW)
    op.drop_column("processo_ren", "despachado_em")
