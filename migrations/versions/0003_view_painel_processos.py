"""view vw_painel_processos: uma linha por processo, no formato da planilha

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Como ler:
#  - processos é a tabela central; clientes e as tabelas de detalhe entram com LEFT JOIN
#    (cada processo tem só UM detalhe, o do seu tipo; os outros dois vêm vazios)
#  - solicitantes tem várias linhas por processo; o GROUP BY junta todas numa linha só,
#    e count/string_agg/bool_and resumem o grupo
#  - os formulários DS-160 são contados numa subconsulta à parte: se entrassem no mesmo JOIN,
#    cada solicitante repetiria a linha do processo e a contagem de solicitantes sairia errada
VIEW = """
CREATE VIEW vw_painel_processos AS
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
    p.atualizado_em
FROM processos p
JOIN clientes c            ON c.id = p.cliente_id
LEFT JOIN processo_obt  o  ON o.processo_id  = p.id
LEFT JOIN processo_ren  r  ON r.processo_id  = p.id
LEFT JOIN processo_pass pa ON pa.processo_id = p.id
LEFT JOIN solicitantes  s  ON s.processo_id  = p.id
LEFT JOIN (
    SELECT s2.processo_id, count(*) AS total
    FROM formularios_ds160 fd
    JOIN solicitantes s2 ON s2.id = fd.solicitante_id
    GROUP BY s2.processo_id
) f ON f.processo_id = p.id
GROUP BY p.id, c.id, o.processo_id, r.processo_id, pa.processo_id
"""


def upgrade() -> None:
    op.execute(VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW vw_painel_processos")
