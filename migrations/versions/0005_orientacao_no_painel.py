"""painel: orientação (status, data e quem orientou) para os processos OBT

Revision ID: 0005
Revises: 0004
"""
import importlib.util
from pathlib import Path

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# Mesma view da 0003 + 3 colunas no FINAL (CREATE OR REPLACE VIEW só aceita acrescentar colunas ao fim).
# O JOIN com usuarios traz o nome de quem deu a orientação; u.id entra no GROUP BY porque o nome
# depende dele (cada processo tem no máximo uma orientação, então a contagem de solicitantes não muda).
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
    u.nome                                                      AS orientacao_por
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
    op.execute(VIEW)


def downgrade() -> None:
    # volta à view da 0003 (sem as colunas de orientação): precisa recriar, não dá para tirar colunas
    caminho = Path(__file__).with_name("0003_view_painel_processos.py")
    spec = importlib.util.spec_from_file_location("migration_0003", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    op.execute("DROP VIEW vw_painel_processos")
    op.execute(modulo.VIEW)
