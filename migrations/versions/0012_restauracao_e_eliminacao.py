"""restaurar cliente excluido e eliminar definitivamente (so por acao manual do admin)

Revision ID: 0012
Revises: 0011

Três mudanças:
  1. O histórico de situações (`eventos`) passa a ser auditado. Sem isso, restaurar um cliente excluído
     traria o processo sem a linha do tempo dele.
  2. A auditoria ganha a ação 'eliminou': a "lápide" que prova que um cliente foi eliminado, sem nenhum dado
     pessoal (só o número, quem fez, quando e o motivo).
  3. A função `eliminar_cliente()`: a ÚNICA forma de apagar linhas da auditoria. Ela remove tudo o que a
     auditoria guarda daquele cliente (inclusive a cópia dos dados que ele tinha) e deixa a lápide.
     A tabela continua recusando UPDATE e DELETE comuns: só esta função liga a exceção, dentro da transação.
"""
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# o mesmo corpo da 0011, com um ramo novo para `eventos` (o processo vem na própria coluna processo_id)
FUNCAO_AUDITAR = r"""
CREATE OR REPLACE FUNCTION auditar() RETURNS trigger LANGUAGE plpgsql AS $$
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
        v_linha := to_jsonb(NEW); v_acao := 'editou';
        SELECT jsonb_object_agg(o.chave, o.valor), jsonb_object_agg(n.chave, n.valor)
          INTO v_antes, v_depois
          FROM jsonb_each(to_jsonb(OLD)) AS o(chave, valor)
          JOIN jsonb_each(v_linha) AS n(chave, valor) ON n.chave = o.chave
         WHERE o.valor IS DISTINCT FROM n.valor AND o.chave <> 'atualizado_em';
        IF v_depois IS NULL THEN
            RETURN NULL;
        END IF;
    END IF;

    v_registro := (v_linha ->> TG_ARGV[0])::integer;

    CASE TG_TABLE_NAME
        WHEN 'clientes' THEN
            v_cliente := v_registro;
        WHEN 'processos' THEN
            v_processo := v_registro;
            v_cliente := (v_linha ->> 'cliente_id')::integer;
        WHEN 'solicitantes', 'eventos' THEN
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

# a versão da 0011: nunca deixa apagar nem editar
GUARDA_ANTIGA = r"""
CREATE OR REPLACE FUNCTION auditoria_somente_acrescenta() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'A auditoria não pode ser alterada nem apagada';
END
$$;
"""

# agora: apagar só quando a eliminação definitiva liga a exceção (dentro da transação, só nesta função)
GUARDA_NOVA = r"""
CREATE OR REPLACE FUNCTION auditoria_somente_acrescenta() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('app.eliminando', true) = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'A auditoria não pode ser alterada nem apagada';
END
$$;
"""

FUNCAO_ELIMINAR = r"""
CREATE FUNCTION eliminar_cliente(p_cliente integer, p_usuario integer, p_motivo text) RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    v_processos integer[];
    v_removidas integer;
BEGIN
    -- só se elimina quem já foi excluído (dois passos: excluir e, depois, eliminar)
    IF EXISTS (SELECT 1 FROM clientes WHERE id = p_cliente) THEN
        RAISE EXCEPTION 'O cliente ainda está no sistema: exclua-o antes de eliminar definitivamente';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM auditoria WHERE tabela = 'clientes' AND registro_id = p_cliente
                   AND acao = 'apagou') THEN
        RAISE EXCEPTION 'Não há registro de exclusão deste cliente';
    END IF;

    SELECT COALESCE(array_agg(DISTINCT registro_id), '{}') INTO v_processos
      FROM auditoria WHERE tabela = 'processos' AND cliente_id = p_cliente;

    PERFORM set_config('app.eliminando', 'on', true);
    DELETE FROM auditoria
     WHERE cliente_id = p_cliente
        OR processo_id = ANY(v_processos)
        OR (tabela = 'processos' AND registro_id = ANY(v_processos))
        -- linhas de OUTROS clientes que só citam um processo deste (a tentativa anterior que perdeu o vínculo)
        OR ((antes ->> 'processo_anterior_id') ~ '^[0-9]+$'
            AND (antes ->> 'processo_anterior_id')::integer = ANY(v_processos))
        OR ((depois ->> 'processo_anterior_id') ~ '^[0-9]+$'
            AND (depois ->> 'processo_anterior_id')::integer = ANY(v_processos));
    GET DIAGNOSTICS v_removidas = ROW_COUNT;
    PERFORM set_config('app.eliminando', 'off', true);

    -- cache de respostas de criação (guardam dados de cliente por até 24 h): só serve para evitar duplicidade
    DELETE FROM chaves_idempotencia;

    -- a lápide: prova que a eliminação aconteceu, sem nenhum dado do cliente
    INSERT INTO auditoria (tabela, registro_id, cliente_id, acao, depois, usuario_id, requisicao, origem)
    VALUES ('clientes', p_cliente, p_cliente, 'eliminou',
            jsonb_build_object('motivo', p_motivo, 'linhas_removidas', v_removidas,
                               'processos', COALESCE(array_length(v_processos, 1), 0)),
            p_usuario, NULLIF(current_setting('app.requisicao', true), ''), 'api');
    RETURN v_removidas;
END
$$;
"""


def upgrade() -> None:
    op.execute(FUNCAO_AUDITAR)
    op.execute("CREATE TRIGGER auditar AFTER INSERT OR UPDATE OR DELETE ON eventos "
               "FOR EACH ROW EXECUTE FUNCTION auditar('id')")
    op.execute("ALTER TABLE auditoria DROP CONSTRAINT ck_auditoria_acao")
    op.execute("ALTER TABLE auditoria ADD CONSTRAINT ck_auditoria_acao "
               "CHECK (acao IN ('criou', 'editou', 'apagou', 'eliminou'))")
    op.execute(GUARDA_NOVA)
    op.execute(FUNCAO_ELIMINAR)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS eliminar_cliente(integer, integer, text)")
    op.execute(GUARDA_ANTIGA)
    op.execute("DROP TRIGGER IF EXISTS auditar ON eventos")
    # a 0011 não conhece eventos nem lápides: sem isto o CHECK antigo recusaria as linhas novas
    op.execute("ALTER TABLE auditoria DISABLE TRIGGER somente_acrescenta")
    op.execute("DELETE FROM auditoria WHERE tabela = 'eventos' OR acao = 'eliminou'")
    op.execute("ALTER TABLE auditoria ENABLE TRIGGER somente_acrescenta")
    op.execute("ALTER TABLE auditoria DROP CONSTRAINT ck_auditoria_acao")
    op.execute("ALTER TABLE auditoria ADD CONSTRAINT ck_auditoria_acao "
               "CHECK (acao IN ('criou', 'editou', 'apagou'))")
    # a função auditar() volta ao corpo da 0011 (sem o ramo de eventos, que já não é chamado)
