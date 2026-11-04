from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from sqlalchemy.exc import IntegrityError, OperationalError

from app import db
from app.routers import clientes, painel, processos, solicitantes


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    # liga a sessão ao banco ao subir o servidor; nos testes ela já vem ligada ao banco de teste
    if db.Session.kw.get("bind") is None:
        db.configurar()
    yield


app = FastAPI(title="Concept Visa Workflow", lifespan=ciclo_de_vida)

app.include_router(clientes.router)
app.include_router(processos.router_obt)
app.include_router(processos.router_ren)
app.include_router(processos.router_pass)
app.include_router(solicitantes.router)
app.include_router(painel.router)


# Rede de segurança: as regras já são checadas antes de gravar, mas o banco é a palavra final
# (duas requisições simultâneas podem passar pela checagem ao mesmo tempo). Traduzimos o erro dele.
@app.exception_handler(IntegrityError)
def violacao_de_regra(request: Request, erro: IntegrityError):
    if isinstance(erro.orig, UniqueViolation):
        return JSONResponse(status_code=409, content={"detail": "Já existe um registro com esses dados"})
    if isinstance(erro.orig, ForeignKeyViolation):
        return JSONResponse(status_code=409,
                            content={"detail": "O registro está vinculado a outros ou o vínculo não existe"})
    return JSONResponse(status_code=422, content={"detail": "Os dados violam uma regra do banco"})


@app.exception_handler(OperationalError)
def banco_indisponivel(request: Request, erro: OperationalError):
    return JSONResponse(status_code=503, content={"detail": "Banco de dados indisponível"})
