"""auditoria: toda mudanca em clientes, processos, pessoas e DS-160, com antes e depois

Revision ID: 0011
Revises: 0010

Quem grava é o próprio PostgreSQL (trigger), e não a API. Assim nada escapa: edição pela API, remoção em
cascata, UPDATE em massa e até edição manual no psql (essa fica com origem 'banco' e sem usuário).

A API conta ao banco quem está mexendo no início de cada transação (`set_config('app.usuario_id', ...)`,
veja app/auditoria.py). O trigger lê esses valores ao gravar.

A tabela não tem chave estrangeira para os registros auditados: o rastro precisa sobreviver à remoção.
Nada é apagado por prazo (decisão do negócio: clientes antigos voltam e o histórico é útil).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

# tabela -> coluna que identifica a linha (os detalhes do processo usam processo_id como chave)
AUDITADAS = {
    "clientes": "id",
    "processos": "id",
    "processo_obt": "processo_id",
    "processo_ren": "processo_id",
    "processo_pass": "processo_id",
    "solicitantes": "id",
    "formularios_ds160": "id",
}

FUNCAO_AUDITAR = r"""
CREATE FUNCTION auditar() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_linha    jsonb;
    v_antes    jsonb;
    v_depois   jsonb;
    v_acao     text;
    v_registro integer;
    v_processo integer;
    v_cliente  integer;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_linha := to_jsonb(NEW); v_depois := v_linha; v_acao := 'criou';
    ELSIF TG_OP = 'DELETE' THEN
        v_linha := to_jsonb(OLD); v_antes := v_linha; v_acao := 'apagou';
    ELSE
        -- edição: só os campos que mudaram (atualizado_em muda sempre e não diz nada)
        v_linha := to_jsonb(NEW); v_acao := 'editou';
        SELECT jsonb_object_agg(o.chave, o.valor), jsonb_object_agg(n.chave, n.valor)
          INTO v_antes, v_depois
          FROM jsonb_each(to_jsonb(OLD)) AS o(chave, valor)
          JOIN jsonb_each(v_linha) AS n(chave, valor) ON n.chave = o.chave
         WHERE o.valor IS DISTINCT FROM n.valor AND o.chave <> 'atualizado_em';
        IF v_depois IS NULL THEN
            RETURN NULL;  -- UPDATE que não mudou nada: não é uma alteração
        END IF;
    END IF;

    v_registro := (v_linha ->> TG_ARGV[0])::integer;

    -- contexto: a que processo e a que cliente a linha pertence (para montar o histórico de cada um).
    -- Se o pai já foi apagado (cascada feita pelo banco), procura na própria auditoria.
    CASE TG_TABLE_NAME
        WHEN 'clientes' THEN
            v_cliente := v_registro;
        WHEN 'processos' THEN
            v_processo := v_registro;
            v_cliente := (v_linha ->> 'cliente_id')::integer;
        WHEN 'solicitantes' THEN
            v_processo := (v_linha ->> 'processo_id')::integer;
        WHEN 'formularios_ds160' THEN
            SELECT s.processo_id INTO v_processo FROM solicitantes s
             WHERE s.id = (v_linha ->> 'solicitante_id')::integer;
            IF v_processo IS NULL THEN
                SELECT a.processo_id INTO v_processo FROM auditoria a
                 WHERE a.tabela = 'solicitantes' AND a.registro_id = (v_linha ->> 'solicitante_id')::integer
                   AND a.processo_id IS NOT NULL
                 ORDER BY a.id DESC LIMIT 1;
            END IF;
        ELSE  -- processo_obt, processo_ren, processo_pass
            v_processo := v_registro;
    END CASE;

    IF v_cliente IS NULL AND v_processo IS NOT NULL THEN
        SELECT p.cliente_id INTO v_cliente FROM processos p WHERE p.id = v_processo;
        IF v_cliente IS NULL THEN
            SELECT a.cliente_id INTO v_cliente FROM auditoria a
             WHERE a.tabela = 'processos' AND a.registro_id = v_processo AND a.cliente_id IS NOT NULL
             ORDER BY a.id DESC LIMIT 1;
        END IF;
    END IF;

    INSERT INTO auditoria (tabela, registro_id, processo_id, cliente_id, acao, antes, depois,
                           usuario_id, requisicao, origem)
    VALUES (TG_TABLE_NAME, v_registro, v_processo, v_cliente, v_acao, v_antes, v_depois,
            NULLIF(current_setting('app.usuario_id', true), '')::integer,
            NULLIF(current_setting('app.requisicao', true), ''),
            COALESCE(NULLIF(current_setting('app.origem', true), ''), 'banco'));
    RETURN NULL;
END
$$;
"""

FUNCAO_SOMENTE_LEITURA = r"""
CREATE FUNCTION auditoria_somente_acrescenta() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'A auditoria não pode ser alterada nem apagada';
END
$$;
"""


def upgrade() -> None:
    op.create_table(
        "auditoria",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("tabela", sa.String(length=40), nullable=False),
        sa.Column("registro_id", sa.Integer(), nullable=False),
        sa.Column("processo_id", sa.Integer(), nullable=True),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("acao", sa.String(length=10), nullable=False),
        sa.Column("antes", postgresql.JSONB(), nullable=True),
        sa.Column("depois", postgresql.JSONB(), nullable=True),
        # sem FK: a auditoria nunca pode impedir (nem ser apagada por) uma operação em outra tabela
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("requisicao", sa.String(length=64), nullable=True),
        sa.Column("origem", sa.String(length=20), nullable=False),
        sa.Column("transacao", sa.BigInteger(), server_default=sa.text("txid_current()"), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("acao IN ('criou', 'editou', 'apagou')", name=op.f("ck_auditoria_acao")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auditoria")),
    )
    op.create_index("ix_auditoria_tabela_registro", "auditoria", ["tabela", "registro_id"])
    op.create_index("ix_auditoria_processo_id", "auditoria", ["processo_id"])
    op.create_index("ix_auditoria_cliente_id", "auditoria", ["cliente_id"])

    op.execute(FUNCAO_AUDITAR)
    for tabela, chave in AUDITADAS.items():
        op.execute(f"CREATE TRIGGER auditar AFTER INSERT OR UPDATE OR DELETE ON {tabela} "
                   f"FOR EACH ROW EXECUTE FUNCTION auditar('{chave}')")

    # só acrescenta: ninguém edita nem apaga uma linha de auditoria pela aplicação
    op.execute(FUNCAO_SOMENTE_LEITURA)
    op.execute("CREATE TRIGGER somente_acrescenta BEFORE UPDATE OR DELETE ON auditoria "
               "FOR EACH ROW EXECUTE FUNCTION auditoria_somente_acrescenta()")


def downgrade() -> None:
    for tabela in AUDITADAS:
        op.execute(f"DROP TRIGGER IF EXISTS auditar ON {tabela}")
    op.execute("DROP FUNCTION IF EXISTS auditar()")
    op.drop_table("auditoria")  # leva junto o trigger somente_acrescenta
    op.execute("DROP FUNCTION IF EXISTS auditoria_somente_acrescenta()")
