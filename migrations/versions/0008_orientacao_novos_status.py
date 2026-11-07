"""OBT: três status novos de orientação (Opções enviadas, Decidindo, Escolheu padrão)

Revision ID: 0008
Revises: 0007
"""
import importlib.util
from pathlib import Path

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

ANTIGOS = ["Opt A", "Fornecidas", "Agendada", "Pendente"]
NOVOS = ["Pendente", "Opções enviadas", "Decidindo", "Opt A", "Escolheu padrão", "Agendada", "Fornecidas"]


def _view_da_0007() -> str:
    caminho = Path(__file__).with_name("0007_despachado_em.py")
    spec = importlib.util.spec_from_file_location("migration_0007", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.VIEW


def _trocar(valores: list[str], tamanho: int) -> None:
    # a view usa a coluna: o Postgres não deixa mudar o tipo com ela de pé, então sai e volta igual
    op.execute("DROP VIEW vw_painel_processos")
    op.execute("ALTER TABLE processo_obt DROP CONSTRAINT ck_processo_obt_orientacao")
    op.execute(f"ALTER TABLE processo_obt ALTER COLUMN orientacao TYPE varchar({tamanho})")
    lista = ", ".join("'" + v.replace("'", "''") + "'" for v in valores)
    op.execute(f"ALTER TABLE processo_obt ADD CONSTRAINT ck_processo_obt_orientacao CHECK (orientacao IN ({lista}))")
    op.execute(_view_da_0007())


def upgrade() -> None:
    _trocar(NOVOS, max(len(v) for v in NOVOS))


def downgrade() -> None:
    # os status novos não existiam antes: voltam para Pendente (perde a informação, de propósito)
    op.execute("UPDATE processo_obt SET orientacao = 'Pendente' "
               "WHERE orientacao IN ('Opções enviadas', 'Decidindo', 'Escolheu padrão')")
    _trocar(ANTIGOS, max(len(v) for v in ANTIGOS))
