# Concept Visa Workflow

Sistema de acompanhamento do fluxo de processos de visto (obtenção, renovação e passaporte), com histórico
de situações, usuários e perfis. Projeto 2 trilha de estudos; veja [docs/PLANO.md](docs/PLANO.md) para a
modelagem (DER) e as regras.

> Todos os dados de exemplo deste repositório são fictícios.

## Stack
Python 3.14, SQLAlchemy 2.0 (ORM), Alembic (migrations), PostgreSQL, FastAPI, pytest.

## Mesma base de código, duas máquinas
Só o `.env` e o banco mudam; nada específico de máquina fica no código.

| | Máquina de testes | Máquina real |
|---|---|---|
| Banco | `concept_visa_workflow` (+ `_test`) | `concept_visa_workflow` |
| Dados | seed fictício (etapa 8) | importados localmente, fora do repositório |
| Migrations | `alembic upgrade head` | `alembic upgrade head` |

A migration base cria só a estrutura e os dados de referência (perfis e situações).

## Como rodar
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # preencha DATABASE_URL (senha com @ vira %40)
alembic upgrade head          # cria/atualiza as tabelas
```

## Testes
Rodam num banco só de testes (o nome precisa terminar em `_test`; qualquer outro é recusado) e recriam o
esquema pelas migrations.
```
pytest
```

## API
Com o servidor ligado (`uvicorn app.main:app --reload --env-file .env`), a documentação interativa fica em `/docs`.

| Recurso | Rotas |
|---|---|
| Clientes | `/clientes` (CRUD, busca por nome, grupo, telefone) |
| Processos | `/processos-obt`, `/processos-ren`, `/processos-pass` (CRUD e filtros) |
| Solicitantes | `/processos/{id}/solicitantes`, `/solicitantes/{id}`, `/solicitantes/{id}/titular` |
| DS-160 | `/solicitantes/{id}/formularios-ds160`, `/formularios-ds160/{id}` |
| Painel | `GET /painel`: uma linha por processo, como a planilha (view `vw_painel_processos`) |

Regras: ao criar um processo, o titular (com o nome do cliente), os solicitantes extras e o evento "criado"
são gravados numa transação só. A situação não muda pelo PATCH (rota própria com histórico na etapa 4).

## Estado
Etapas 1 a 3 concluídas: modelagem, SQLAlchemy + Alembic (migrations 0001 a 0003) e CRUD com o painel.
Próxima: workflow de situações com eventos (etapa 4).
