"""consulado obrigatório só na API (OBT) e status_rascunho na renovação

- O histórico do Projeto 1 tem processos OBT com data marcada e consulado N/D (desconhecido). A regra
  "com data, consulado obrigatório" continua valendo na API para cadastros e edições, mas deixa de ser
  uma restrição do banco no OBT, senão esses registros antigos não poderiam ser importados.
- A renovação do Projeto 1 tinha status_rascunho; ele havia ficado de fora do modelo.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("consulado_se_agendado", "processo_obt", type_="check")

    op.add_column("processo_ren", sa.Column("status_rascunho", sa.String(length=8), nullable=False,
                                            server_default="Pendente"))
    op.create_check_constraint("rascunho", "processo_ren",
                               "status_rascunho IN ('Pendente', 'Parcial', 'Enviado')")


def downgrade() -> None:
    op.drop_column("processo_ren", "status_rascunho")  # leva o CHECK junto
    op.create_check_constraint(
        "consulado_se_agendado", "processo_obt",
        "(data_casv IS NULL AND data_entrevista IS NULL) OR consulado IS NOT NULL")
