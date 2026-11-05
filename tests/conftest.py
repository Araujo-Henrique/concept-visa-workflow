"""Testes contra um PostgreSQL de verdade, num banco só de testes (nome termina em _test).

O esquema vem das migrations (`alembic upgrade head`): assim os testes também provam que a migration
base cria o que os modelos esperam.
"""
import os

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import make_url, text

from app import db
from app.models import Cliente, ProcessoOBT, Solicitante

load_dotenv()
# segredo só dos testes (não é o do .env): o token precisa assinar sem depender da máquina
os.environ["JWT_SECRET"] = "segredo-apenas-para-testes-com-mais-de-32-caracteres"

# tabelas com dados de teste; perfis e situacoes são dados de referência e ficam
TABELAS = "eventos, formularios_ds160, solicitantes, processo_obt, processo_ren, processo_pass, " \
          "processos, clientes, usuarios"


@pytest.fixture(scope="session")
def engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.exit("Defina TEST_DATABASE_URL (veja .env.example)", returncode=2)
    if not (make_url(url).database or "").endswith("_test"):
        pytest.exit("TEST_DATABASE_URL precisa apontar para um banco cujo nome termina em _test", returncode=2)

    engine = db.configurar(url)
    # Começa do zero: recria o esquema (apaga tabelas, view e alembic_version) e sobe todas as migrations.
    # Não usamos `downgrade base` porque ele falha de propósito se sobraram dados que o passo não desfaz.
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    config = Config("alembic.ini")
    # o configparser do Alembic usa % como sintaxe própria: o %40 da senha precisa virar %%40
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def sessao(engine):
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABELAS} RESTART IDENTITY CASCADE"))
    with db.Session() as sessao:
        yield sessao


SENHA_TESTE = "senha-de-teste-123"


@pytest.fixture
def usuario_teste(sessao):
    """Usuário admin ativo, criado no banco de teste para as requisições autenticadas."""
    from app.servicos.usuarios import criar_usuario
    usuario = criar_usuario(sessao, "Usuario Teste", "teste@exemplo.com", "admin", SENHA_TESTE)
    sessao.commit()
    return usuario


@pytest.fixture
def client_anonimo(sessao):
    """Cliente HTTP SEM login. Sem `with`, o lifespan não roda: a sessão continua ligada ao banco de teste,
    nunca ao DATABASE_URL."""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def client(client_anonimo, usuario_teste):
    """Cliente HTTP já logado como `usuario_teste`: todas as requisições levam o token."""
    from app.seguranca import criar_token
    client_anonimo.headers["Authorization"] = f"Bearer {criar_token(usuario_teste.id)}"
    return client_anonimo


@pytest.fixture
def cliente(sessao):
    c = Cliente(nome="Ana Souza", telefone="41999999999")
    sessao.add(c)
    sessao.commit()
    return c


def novo_obt(cliente, **extra):
    """ProcessoOBT válido com um titular; `extra` sobrescreve campos."""
    from app.enums import Consulado, Orientacao, Rascunho
    campos = dict(cliente_id=cliente.id, situacao="Processando", consulado=Consulado.SP,
                  status_rascunho=Rascunho.PENDENTE, orientacao=Orientacao.PENDENTE)
    campos.update(extra)
    processo = ProcessoOBT(**campos)
    processo.solicitantes.append(Solicitante(nome=cliente.nome, titular=True))
    return processo
