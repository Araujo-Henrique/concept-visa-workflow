"""OBT: o status de orientação "Decidindo" passa a se chamar "Sem resposta"

Revision ID: 0009
Revises: 0008
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

ANTES = ["Pendente", "Opções enviadas", "Decidindo", "Opt A", "Escolheu padrão", "Agendada", "Fornecidas"]
DEPOIS = ["Pendente", "Opções enviadas", "Sem resposta", "Opt A", "Escolheu padrão", "Agendada", "Fornecidas"]


def _trocar(de: str, para: str, valores: list[str]) -> None:
    # o tamanho da coluna (15) já comporta os dois nomes: só a regra (CHECK) e os dados mudam
    op.execute("ALTER TABLE processo_obt DROP CONSTRAINT ck_processo_obt_orientacao")
    op.execute(f"UPDATE processo_obt SET orientacao = '{para}' WHERE orientacao = '{de}'")
    lista = ", ".join(f"'{v}'" for v in valores)
    op.execute(f"ALTER TABLE processo_obt ADD CONSTRAINT ck_processo_obt_orientacao CHECK (orientacao IN ({lista}))")


def upgrade() -> None:
    _trocar("Decidindo", "Sem resposta", DEPOIS)


def downgrade() -> None:
    _trocar("Sem resposta", "Decidindo", ANTES)
