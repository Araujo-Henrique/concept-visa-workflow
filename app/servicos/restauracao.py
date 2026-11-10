"""Clientes excluídos: listar, restaurar e eliminar de vez. Só o admin chega aqui (a rota exige `administrar`).

Como a restauração funciona: a auditoria guarda a linha inteira de tudo o que foi apagado (cliente, processos,
pessoas, DS-160 e histórico de situações). Restaurar é recolocar essas linhas, com os mesmos números (id), na
ordem que as chaves estrangeiras pedem, e religar as "tentativas anteriores" que a exclusão desfez. O
PostgreSQL converte o JSON de volta em colunas (`jsonb_populate_record`), então datas e tipos voltam iguais.
Tudo numa transação: ou volta completo, ou não volta nada.

Eliminar de vez: a função `eliminar_cliente()` do banco (migration 0012) apaga também a cópia na auditoria.
"""
import json

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import auditoria
from app.db import Base
from app.models import Cliente, Usuario
from app.servicos.workflow import ErroDeRegra

# a ordem das chaves estrangeiras: o pai antes dos filhos
ORDEM = ("clientes", "processos", "processo_obt", "processo_ren", "processo_pass", "solicitantes",
         "formularios_ds160", "eventos")

_ULTIMAS_EXCLUSOES = """
    SELECT DISTINCT ON (a.registro_id) a.*
      FROM auditoria a
     WHERE a.tabela = 'clientes' AND a.acao = 'apagou'
       AND NOT EXISTS (SELECT 1 FROM clientes c WHERE c.id = a.registro_id)
     ORDER BY a.registro_id, a.id DESC
"""


def _igual(a: str, b: str) -> bool:
    """Compara nomes sem diferenciar maiúsculas nem espaços repetidos (como a confirmação da tela)."""
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()


def listar_apagados(sessao: Session, limit: int, offset: int) -> tuple[list[dict], int]:
    """Clientes que hoje não existem mais e ainda têm cópia na auditoria, do excluído mais recente ao mais antigo."""
    total = sessao.scalar(text(f"SELECT count(*) FROM ({_ULTIMAS_EXCLUSOES}) u"))
    linhas = sessao.execute(text(f"""
        SELECT u.registro_id AS cliente_id, u.antes ->> 'nome' AS nome, u.antes ->> 'telefone' AS telefone,
               u.antes ->> 'email' AS email, u.criado_em AS apagado_em, u.usuario_id,
               us.nome AS apagado_por, u.origem,
               (SELECT count(*) FROM auditoria p WHERE p.transacao = u.transacao AND p.tabela = 'processos'
                   AND p.acao = 'apagou' AND p.cliente_id = u.registro_id) AS n_processos
          FROM ({_ULTIMAS_EXCLUSOES}) u LEFT JOIN usuarios us ON us.id = u.usuario_id
         ORDER BY u.criado_em DESC, u.registro_id DESC LIMIT :limit OFFSET :offset"""),
        {"limit": limit, "offset": offset}).mappings().all()
    return [dict(linha) for linha in linhas], total


def _ultima_exclusao(sessao: Session, cliente_id: int):
    if sessao.get(Cliente, cliente_id) is not None:
        raise ErroDeRegra("Este cliente está no sistema: só dá para restaurar ou eliminar quem foi excluído", 409)
    exclusao = sessao.execute(text(
        "SELECT id, transacao, antes FROM auditoria WHERE tabela = 'clientes' AND registro_id = :c "
        "AND acao = 'apagou' ORDER BY id DESC LIMIT 1"), {"c": cliente_id}).first()
    if exclusao is None:
        raise ErroDeRegra("Não há cópia deste cliente (ele nunca foi excluído ou já foi eliminado definitivamente)",
                          404)
    return exclusao


def restaurar_cliente(sessao: Session, cliente_id: int, admin: Usuario) -> dict:
    exclusao = _ultima_exclusao(sessao, cliente_id)
    nome = exclusao.antes["nome"]
    if sessao.scalar(select(Cliente.id).where(func.lower(Cliente.nome) == nome.lower())) is not None:
        raise ErroDeRegra(f"Já existe outro cliente chamado '{nome}'. Renomeie ou exclua o atual antes de restaurar",
                          409)

    # na auditoria, o que veio desta restauração fica marcado como tal
    auditoria.identificar(sessao, usuario_id=admin.id, origem="restauracao")

    processos = [r[0] for r in sessao.execute(text(
        "SELECT registro_id FROM auditoria WHERE transacao = :t AND tabela = 'processos' AND acao = 'apagou' "
        "AND cliente_id = :c"), {"t": exclusao.transacao, "c": cliente_id})]
    linhas = sessao.execute(text(
        "SELECT id, tabela FROM auditoria WHERE transacao = :t AND acao = 'apagou' "
        "AND tabela = ANY(CAST(:tabelas AS text[])) AND (cliente_id = :c OR processo_id = ANY(CAST(:ps AS integer[]))) "
        "ORDER BY id"), {"t": exclusao.transacao, "tabelas": list(ORDEM), "c": cliente_id, "ps": processos}).all()
    linhas.sort(key=lambda linha: (ORDEM.index(linha.tabela), linha.id))

    recolocadas: dict[str, int] = {}
    try:
        for linha in linhas:
            tabela = Base.metadata.tables[linha.tabela]
            # colunas calculadas pelo banco (ex.: data_despacho) não se gravam
            colunas = ", ".join(f'"{c.name}"' for c in tabela.columns if c.computed is None)
            sessao.execute(text(
                f'INSERT INTO "{linha.tabela}" ({colunas}) SELECT {colunas} FROM '
                f'jsonb_populate_record(NULL::"{linha.tabela}", (SELECT antes FROM auditoria WHERE id = :id))'),
                {"id": linha.id})
            recolocadas[linha.tabela] = recolocadas.get(linha.tabela, 0) + 1

        # a exclusão desfez as "tentativas anteriores" antes de apagar: religa, se os dois lados existem de novo
        vinculos = 0
        desfeitos = sessao.execute(text(
            "SELECT registro_id, (antes ->> 'processo_anterior_id')::integer AS anterior FROM auditoria "
            "WHERE transacao = :t AND tabela = 'processos' AND acao = 'editou' "
            "AND (antes ->> 'processo_anterior_id') IS NOT NULL "
            "AND (depois -> 'processo_anterior_id') = 'null'::jsonb"), {"t": exclusao.transacao}).all()
        for desfeito in desfeitos:
            vinculos += sessao.execute(text(
                "UPDATE processos SET processo_anterior_id = :anterior WHERE id = :id "
                "AND processo_anterior_id IS NULL AND EXISTS (SELECT 1 FROM processos WHERE id = :anterior)"),
                {"anterior": desfeito.anterior, "id": desfeito.registro_id}).rowcount
    except IntegrityError:
        # algo que foi liberado pela exclusão voltou a existir (ex.: um código de DS-160 usado em outro lugar)
        raise ErroDeRegra("Não deu para restaurar: um dado único deste cliente (como o código de um DS-160) já está "
                          "em uso. Nada foi alterado", 409)
    return {"cliente_id": cliente_id, "nome": nome, "processos": recolocadas.get("processos", 0),
            "pessoas": recolocadas.get("solicitantes", 0), "formularios": recolocadas.get("formularios_ds160", 0),
            "eventos": recolocadas.get("eventos", 0), "vinculos": vinculos}


def eliminar_definitivamente(sessao: Session, cliente_id: int, motivo: str, nome_confirmado: str,
                             admin: Usuario) -> int:
    """Apaga o cliente também da auditoria (quem já foi excluído). Devolve quantas linhas de auditoria saíram."""
    exclusao = _ultima_exclusao(sessao, cliente_id)
    if not _igual(nome_confirmado, exclusao.antes["nome"]):
        raise ErroDeRegra("O nome digitado não confere com o do cliente", 422)
    return sessao.scalar(text("SELECT eliminar_cliente(:c, :u, :m)"),
                         {"c": cliente_id, "u": admin.id, "m": motivo.strip()})
