"""Painel: status do DS-160 de cada processo (o menos avançado do grupo) e quantos já estão fechados

Um processo pode ter vários formulários (um por pessoa, às vezes mais de um por pessoa). Para ver de relance
"em que pé está o DS-160", a view traz:
  - ds160_status: o status MENOS avançado entre os formulários do processo. É o gargalo: o processo só está
    pronto quando todos estão Fechado. Sem nenhum formulário, vem nulo.
  - ds160_fechados: quantos formulários já estão Fechado (com n_formularios, dá o "2 de 3").

A ordem de avanço (Pendente < Parcial < Aberto < Preenchido < Revisado < Fechado) é a de app.enums.StatusDS.
Se um status novo for criado lá, ele precisa entrar neste CASE (tests/test_ds160_no_painel.py confere).

Revision ID: 0015
Revises: 0014
"""
import importlib.util
from pathlib import Path

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

# Mesma view da 0014 + ds160_status e ds160_fechados no FINAL (CREATE OR REPLACE VIEW só acrescenta colunas ao fim).
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
    o.previsao_orientacao,
    max(f.menos_avancado)                                       AS ds160_status,
    coalesce(max(f.fechados), 0)                                AS ds160_fechados
FROM processos p
JOIN clientes c            ON c.id = p.cliente_id
LEFT JOIN processo_obt  o  ON o.processo_id  = p.id
LEFT JOIN processo_ren  r  ON r.processo_id  = p.id
LEFT JOIN processo_pass pa ON pa.processo_id = p.id
LEFT JOIN usuarios      u  ON u.id = o.orientacao_por_id
LEFT JOIN solicitantes  s  ON s.processo_id  = p.id
LEFT JOIN (
    SELECT s2.processo_id,
           count(*)                                      AS total,
           count(*) FILTER (WHERE fd.status = 'Fechado') AS fechados,
           (array_agg(fd.status ORDER BY CASE fd.status
                WHEN 'Pendente'    THEN 1
                WHEN 'Parcial'     THEN 2
                WHEN 'Aberto'      THEN 3
                WHEN 'Preenchido'  THEN 4
                WHEN 'Revisado'    THEN 5
                WHEN 'Fechado'     THEN 6
                ELSE 0 END))[1]                          AS menos_avancado
    FROM formularios_ds160 fd
    JOIN solicitantes s2 ON s2.id = fd.solicitante_id
    GROUP BY s2.processo_id
) f ON f.processo_id = p.id
GROUP BY p.id, c.id, o.processo_id, r.processo_id, pa.processo_id, u.id
"""


def upgrade() -> None:
    op.execute(VIEW)


def downgrade() -> None:
    caminho = Path(__file__).with_name("0014_previsao_orientacao.py")
    spec = importlib.util.spec_from_file_location("migration_0014", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    op.execute("DROP VIEW vw_painel_processos")
    op.execute(modulo.VIEW)
