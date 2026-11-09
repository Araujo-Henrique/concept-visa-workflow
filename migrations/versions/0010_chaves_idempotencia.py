"""chaves de idempotencia: reenviar a mesma criacao nao cria duas vezes

Revision ID: 0010
Revises: 0009
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chaves_idempotencia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("chave", sa.String(length=80), nullable=False),
        sa.Column("escopo", sa.String(length=200), nullable=False),
        sa.Column("impressao", sa.String(length=64), nullable=False),
        sa.Column("status", sa.Integer(), nullable=True),
        sa.Column("corpo", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE",
                                name=op.f("fk_chaves_idempotencia_usuario_id_usuarios")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chaves_idempotencia")),
        sa.UniqueConstraint("usuario_id", "chave", name="uq_chaves_idempotencia_usuario_chave"),
    )
    op.create_index("ix_chaves_idempotencia_criado_em", "chaves_idempotencia", ["criado_em"])


def downgrade() -> None:
    op.drop_index("ix_chaves_idempotencia_criado_em", table_name="chaves_idempotencia")
    op.drop_table("chaves_idempotencia")
