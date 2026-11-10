"""versao do token: trocar a senha ou desativar a pessoa encerra as sessoes que ja existiam

Revision ID: 0013
Revises: 0012

Cada usuario ganha `token_version` (comeca em 0). O numero vai dentro do token ao entrar e a API compara com o do
banco a cada requisicao: se subiu, o token e recusado (401). Quem sobe o numero: trocar ou redefinir a senha,
desativar o usuario e perder o perfil de admin. Tokens emitidos antes desta migration nao tem o numero e valem
como versao 0, entao continuam funcionando ate a primeira dessas mudancas.
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("token_version", sa.Integer(), server_default=sa.text("0"), nullable=False))


def downgrade() -> None:
    op.drop_column("usuarios", "token_version")
