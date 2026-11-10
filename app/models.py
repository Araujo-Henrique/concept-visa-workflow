"""Modelos do banco (SQLAlchemy 2.0).

Cada classe é uma tabela. `relationship` não cria coluna: só deixa navegar entre objetos
(processo.solicitantes) usando a chave estrangeira que já existe.
"""
from datetime import date, datetime

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Computed, Date, DateTime, Enum, ForeignKey,
                        ForeignKeyConstraint, Identity, Index, Integer, String, Text, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import (Consulado, DocsREN, Monitoramento, Orientacao, Rascunho, Resultado,
                       StatusDS, TipoEvento)


def coluna_enum(enum, nome: str):
    """Enum do Python guardado como texto + CHECK no banco (mais simples de migrar que enum nativo)."""
    return Enum(enum, name=nome, native_enum=False, create_constraint=True,
                length=max(len(e.value) for e in enum),
                values_callable=lambda e: [x.value for x in e])


# ---------------------------------------------------------------- acesso

class Perfil(Base):
    __tablename__ = "perfis"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(30), unique=True)


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        # e-mail único sem diferenciar maiúsculas
        Index("uq_usuarios_email_lower", func.lower(text("email")), unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200))
    senha_hash: Mapped[str | None] = mapped_column(String(200))  # nulo = só entra com Google
    perfil_id: Mapped[int] = mapped_column(ForeignKey("perfis.id"))
    ativo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    perfil: Mapped[Perfil] = relationship()


# ---------------------------------------------------------------- clientes

class Cliente(Base):
    __tablename__ = "clientes"
    __table_args__ = (
        Index("uq_clientes_nome_lower", func.lower(text("nome")), unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    telefone: Mapped[str | None] = mapped_column(String(20))
    grupo: Mapped[str | None] = mapped_column(String(100))

    processos: Mapped[list["Processo"]] = relationship(back_populates="cliente")


# ---------------------------------------------------------------- processos

class Situacao(Base):
    """Situações válidas por tipo de processo (dado de referência, carregado na migration)."""
    __tablename__ = "situacoes"

    tipo: Mapped[str] = mapped_column(String(4), primary_key=True)
    nome: Mapped[str] = mapped_column(String(40), primary_key=True)


class Processo(Base):
    """Parte comum a todo processo. Cada tipo tem uma tabela de detalhe 1:1 (herança de tabela unida):
    consultar `session.get(Processo, 7)` devolve já um ProcessoOBT, ProcessoREN ou ProcessoPASS."""
    __tablename__ = "processos"
    __table_args__ = (
        CheckConstraint("tipo IN ('OBT','REN','PASS')", name="tipo"),
        UniqueConstraint("id", "tipo", name="uq_processos_id_tipo"),  # alvo da FK composta dos detalhes
        ForeignKeyConstraint(["tipo", "situacao"], ["situacoes.tipo", "situacoes.nome"],
                             name="fk_processos_tipo_situacao_situacoes"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(4))
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))
    situacao: Mapped[str] = mapped_column(String(40))
    processo_anterior_id: Mapped[int | None] = mapped_column(ForeignKey("processos.id"))  # nova tentativa
    observacao: Mapped[str | None] = mapped_column(Text)  # notas livres (ex.: alterações pedidas no DS-160)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    cliente: Mapped[Cliente] = relationship(back_populates="processos")
    processo_anterior: Mapped["Processo | None"] = relationship(remote_side=[id])
    solicitantes: Mapped[list["Solicitante"]] = relationship(
        back_populates="processo", cascade="all, delete-orphan", order_by="Solicitante.id")
    eventos: Mapped[list["Evento"]] = relationship(
        back_populates="processo", cascade="all, delete-orphan", order_by="Evento.id")

    __mapper_args__ = {"polymorphic_on": "tipo"}


def _fk_detalhe(tipo: str):
    """FK composta (processo_id, tipo) -> processos(id, tipo) + CHECK: um detalhe de REN
    nunca pode apontar para um processo OBT."""
    return (
        ForeignKeyConstraint(["processo_id", "tipo"], ["processos.id", "processos.tipo"], ondelete="CASCADE"),
        CheckConstraint(f"tipo = '{tipo}'", name="tipo"),
    )


class ProcessoOBT(Processo):
    __tablename__ = "processo_obt"
    __table_args__ = (
        *_fk_detalhe("OBT"),
        CheckConstraint("orientacao <> 'Agendada' OR orientacao_data IS NOT NULL", name="agendada_exige_data"),
        # consulado pode ficar vazio. A regra "com data, o consulado é obrigatório" vale na API: o histórico
        # importado tem processos com data marcada e consulado desconhecido (N/D), então o banco não a impõe.
    )
    __mapper_args__ = {"polymorphic_identity": "OBT"}

    processo_id: Mapped[int] = mapped_column(primary_key=True)
    tipo_fk: Mapped[str] = mapped_column("tipo", String(4), default="OBT")
    consulado: Mapped[Consulado | None] = mapped_column(coluna_enum(Consulado, "consulado"))
    monitoramento: Mapped[Monitoramento] = mapped_column(
        coluna_enum(Monitoramento, "monitoramento"), default=Monitoramento.ATIVO)
    data_casv: Mapped[date | None] = mapped_column(Date)
    data_entrevista: Mapped[date | None] = mapped_column(Date)
    data_vencimento_taxa: Mapped[date | None] = mapped_column(Date)
    status_rascunho: Mapped[Rascunho] = mapped_column(coluna_enum(Rascunho, "rascunho"))
    orientacao: Mapped[Orientacao] = mapped_column(coluna_enum(Orientacao, "orientacao"))
    orientacao_data: Mapped[date | None] = mapped_column(Date)
    orientacao_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    codigo_rastreio: Mapped[str | None] = mapped_column(String(60))


class ProcessoREN(Processo):
    __tablename__ = "processo_ren"
    __table_args__ = (
        *_fk_detalhe("REN"),
        CheckConstraint("data_casv IS NULL OR consulado IS NOT NULL", name="consulado_se_agendado"),
    )
    __mapper_args__ = {"polymorphic_identity": "REN"}

    processo_id: Mapped[int] = mapped_column(primary_key=True)
    tipo_fk: Mapped[str] = mapped_column("tipo", String(4), default="REN")
    consulado: Mapped[Consulado | None] = mapped_column(coluna_enum(Consulado, "consulado"))
    data_casv: Mapped[date | None] = mapped_column(Date)
    # coluna gerada pelo próprio banco: despacho = CASV - 7 dias
    data_despacho: Mapped[date | None] = mapped_column(Date, Computed("data_casv - 7", persisted=True))
    # quando foi despachado de verdade; vazio = ainda falta despachar (a data_despacho é só o prazo)
    despachado_em: Mapped[date | None] = mapped_column(Date)
    docs: Mapped[DocsREN] = mapped_column(coluna_enum(DocsREN, "docs"), default=DocsREN.PENDENTE)
    status_rascunho: Mapped[Rascunho] = mapped_column(
        coluna_enum(Rascunho, "rascunho"), default=Rascunho.PENDENTE, server_default=Rascunho.PENDENTE.value)
    endereco: Mapped[str | None] = mapped_column(Text)
    codigo_rastreio: Mapped[str | None] = mapped_column(String(60))


class ProcessoPASS(Processo):
    __tablename__ = "processo_pass"
    __table_args__ = _fk_detalhe("PASS")
    __mapper_args__ = {"polymorphic_identity": "PASS"}

    processo_id: Mapped[int] = mapped_column(primary_key=True)
    tipo_fk: Mapped[str] = mapped_column("tipo", String(4), default="PASS")
    data_pf: Mapped[date | None] = mapped_column(Date)
    prazo_pf: Mapped[date | None] = mapped_column(Date)


# ---------------------------------------------------------------- solicitantes e formulários

class Solicitante(Base):
    """Uma pessoa dentro de um processo. Várias linhas com o mesmo processo_id = o grupo do processo."""
    __tablename__ = "solicitantes"
    __table_args__ = (
        # no máximo um titular por processo (o "pelo menos um" é garantido pelo serviço)
        Index("uq_solicitantes_um_titular", "processo_id", unique=True, postgresql_where=text("titular")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"))
    nome: Mapped[str] = mapped_column(String(200))
    titular: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    resultado: Mapped[Resultado] = mapped_column(
        coluna_enum(Resultado, "resultado"), default=Resultado.PROCESSANDO)

    processo: Mapped[Processo] = relationship(back_populates="solicitantes")
    formularios: Mapped[list["FormularioDS160"]] = relationship(
        back_populates="solicitante", cascade="all, delete-orphan", order_by="FormularioDS160.id")


class FormularioDS160(Base):
    __tablename__ = "formularios_ds160"
    __table_args__ = (
        CheckConstraint("codigo ~ '^AA00[A-Z0-9]{6}$'", name="formato_codigo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("solicitantes.id", ondelete="CASCADE"))
    codigo: Mapped[str] = mapped_column(String(10), unique=True)
    status: Mapped[StatusDS] = mapped_column(coluna_enum(StatusDS, "status"), default=StatusDS.PENDENTE)
    observacao: Mapped[str | None] = mapped_column(Text)

    solicitante: Mapped[Solicitante] = relationship(back_populates="formularios")


# ---------------------------------------------------------------- histórico

class Evento(Base):
    """Linha do tempo do processo: toda mudança de situação deixa um registro."""
    __tablename__ = "eventos"
    __table_args__ = (
        CheckConstraint("tipo <> 'reaberto' OR length(trim(coalesce(motivo, ''))) > 0", name="reaberto_exige_motivo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    tipo: Mapped[TipoEvento] = mapped_column(coluna_enum(TipoEvento, "tipo"))
    situacao_anterior: Mapped[str | None] = mapped_column(String(40))
    situacao_nova: Mapped[str | None] = mapped_column(String(40))
    motivo: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    processo: Mapped[Processo] = relationship(back_populates="eventos")


class AuditoriaUsuario(Base):
    """Quem mudou o quê num usuário (perfil, ativo, nome, senha) e quando. Não guarda a senha: só que mudou."""
    __tablename__ = "auditoria_usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))  # quem sofreu a mudança
    feito_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))  # quem fez
    campo: Mapped[str] = mapped_column(String(30))
    valor_anterior: Mapped[str | None] = mapped_column(Text)
    valor_novo: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChaveIdempotencia(Base):
    """Pedidos de criação já recebidos (cabeçalho Idempotency-Key). Se o mesmo pedido chega de novo (duplo
    clique, reenvio da rede), a API devolve a resposta guardada em vez de criar outra vez.

    `status` nulo = o pedido ainda está sendo processado. Só respostas de sucesso ficam guardadas;
    as chaves são apagadas depois de 24 h."""
    __tablename__ = "chaves_idempotencia"
    __table_args__ = (
        UniqueConstraint("usuario_id", "chave", name="uq_chaves_idempotencia_usuario_chave"),
        Index("ix_chaves_idempotencia_criado_em", "criado_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    chave: Mapped[str] = mapped_column(String(80))
    escopo: Mapped[str] = mapped_column(String(200))  # "POST /clientes": a mesma chave não vale para outra rota
    impressao: Mapped[str] = mapped_column(String(64))  # sha256 do corpo: mesma chave com dados diferentes é erro
    status: Mapped[int | None] = mapped_column(Integer)
    corpo: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Auditoria(Base):
    """Toda mudança em clientes, processos (e detalhes), solicitantes e DS-160. Quem grava é o trigger do banco
    (migration 0011), nunca a aplicação: aqui o modelo só serve para LER. A tabela só aceita INSERT.

    `antes`/`depois`: o registro inteiro ao criar/apagar; só os campos alterados ao editar.
    `processo_id`/`cliente_id`: a que processo/cliente a linha pertence, mesmo depois de apagados.
    `transacao`: linhas da mesma operação (ex.: um cliente apagado com seus processos) têm o mesmo número."""
    __tablename__ = "auditoria"
    __table_args__ = (
        CheckConstraint("acao IN ('criou', 'editou', 'apagou', 'eliminou')", name="acao"),
        Index("ix_auditoria_tabela_registro", "tabela", "registro_id"),
        Index("ix_auditoria_processo_id", "processo_id"),
        Index("ix_auditoria_cliente_id", "cliente_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    tabela: Mapped[str] = mapped_column(String(40))
    registro_id: Mapped[int] = mapped_column(Integer)
    processo_id: Mapped[int | None] = mapped_column(Integer)
    cliente_id: Mapped[int | None] = mapped_column(Integer)
    acao: Mapped[str] = mapped_column(String(10))
    antes: Mapped[dict | None] = mapped_column(JSONB)
    depois: Mapped[dict | None] = mapped_column(JSONB)
    usuario_id: Mapped[int | None] = mapped_column(Integer)  # sem FK: a auditoria nunca trava outra operação
    requisicao: Mapped[str | None] = mapped_column(String(64))  # o mesmo código do log (X-Request-ID)
    origem: Mapped[str] = mapped_column(String(20))
    transacao: Mapped[int] = mapped_column(BigInteger, server_default=text("txid_current()"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
