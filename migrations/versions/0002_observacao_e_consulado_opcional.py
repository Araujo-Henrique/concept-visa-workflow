"""observacao no processo e consulado opcional até haver data marcada

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("processos", sa.Column("observacao", sa.Text(), nullable=True))

    op.alter_column("processo_obt", "consulado", existing_type=sa.String(length=3), nullable=True)
    op.create_check_constraint(
        "consulado_se_agendado", "processo_obt",
        "(data_casv IS NULL AND data_entrevista IS NULL) OR consulado IS NOT NULL")

    op.alter_column("processo_ren", "consulado", existing_type=sa.String(length=3), nullable=True)
    op.create_check_constraint(
        "consulado_se_agendado", "processo_ren", "data_casv IS NULL OR consulado IS NOT NULL")


def downgrade() -> None:
    op.drop_constraint("ck_processo_ren_consulado_se_agendado", "processo_ren", type_="check")
    op.alter_column("processo_ren", "consulado", existing_type=sa.String(length=3), nullable=False)
    op.drop_constraint("ck_processo_obt_consulado_se_agendado", "processo_obt", type_="check")
    op.alter_column("processo_obt", "consulado", existing_type=sa.String(length=3), nullable=False)
    op.drop_column("processos", "observacao")
