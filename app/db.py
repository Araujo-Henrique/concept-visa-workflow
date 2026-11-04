"""Conexão com o PostgreSQL via SQLAlchemy.

`engine` é o pool de conexões; `Session` é a "unidade de trabalho": tudo o que acontece dentro de um
`with Session() as sessao:` é uma transação (commit grava tudo, erro desfaz tudo).
"""
import os

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

# Nomes previsíveis para constraints: o Alembic precisa deles para alterar/remover no futuro.
CONVENCAO = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCAO)


def url_do_banco() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Defina DATABASE_URL (veja .env.example)")
    return url


def criar_engine(url: str | None = None):
    return create_engine(url or url_do_banco(), pool_pre_ping=True)


Session = sessionmaker(expire_on_commit=False)


def configurar(url: str | None = None):
    """Liga a Session a um banco. A API chama ao subir; os testes chamam com o banco de teste."""
    engine = criar_engine(url)
    Session.configure(bind=engine)
    return engine
