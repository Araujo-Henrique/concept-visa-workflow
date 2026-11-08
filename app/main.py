import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg.errors import ForeignKeyViolation, QueryCanceled, UniqueViolation
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as SemConexaoLivre

from app import db, deps, limites
from app.routers import auth, clientes, painel, processos, referencias, solicitantes, usuarios, workflow


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    # liga a sessão ao banco ao subir o servidor; nos testes ela já vem ligada ao banco de teste
    if db.Session.kw.get("bind") is None:
        db.configurar()
    yield


def _docs_ligados() -> bool:
    # Em produção (VPS), API_DOCS=false tira o /docs e o /openapi.json: o mapa da API não fica à vista.
    return os.environ.get("API_DOCS", "true").strip().lower() not in ("false", "0", "nao", "não")


_docs = _docs_ligados()
app = FastAPI(title="Concept Visa Workflow", lifespan=ciclo_de_vida, docs_url="/docs" if _docs else None,
              redoc_url="/redoc" if _docs else None, openapi_url="/openapi.json" if _docs else None)

LIMITE_CORPO_BYTES = int(os.environ.get("LIMITE_CORPO_KB", "1024")) * 1024


@app.middleware("http")
async def proteger(request: Request, chamar):
    """Antes de qualquer rota (e de qualquer consulta ao banco):
      - corpo grande demais: 413 (nenhuma tela manda mais que alguns KB; isso só serve para entupir o servidor);
      - requisições demais do mesmo IP no último minuto: 429 com Retry-After."""
    tamanho = request.headers.get("content-length")
    if tamanho is not None and (not tamanho.isdigit() or int(tamanho) > LIMITE_CORPO_BYTES):
        return JSONResponse(status_code=413, content={"detail": "Dados grandes demais"})
    if espera := limites.geral.registrar(limites.ip_do_cliente(request)):
        return JSONResponse(status_code=429, headers={"Retry-After": str(espera)},
                            content={"detail": limites.mensagem_de_espera(espera)})
    return await chamar(request)


app.include_router(auth.router)  # login e "quem sou eu": o login é a única rota pública

# Todas as demais exigem login E a permissão do método (GET lê, POST/PATCH escrevem, DELETE apaga).
# Declarar aqui, e não rota a rota, evita esquecer alguma: uma rota nova já nasce protegida.
protegidas = [Depends(deps.autorizar)]
for roteador in (clientes.router, processos.router_obt, processos.router_ren, processos.router_pass,
                 solicitantes.router, workflow.router, painel.router, referencias.router):
    app.include_router(roteador, dependencies=protegidas)
app.include_router(usuarios.router)  # administração: exige a permissão `administrar` (só admin)


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
    if isinstance(erro.orig, QueryCanceled):  # passou do statement_timeout (DB_TEMPO_MAXIMO_CONSULTA_MS)
        return JSONResponse(status_code=503,
                            content={"detail": "A consulta demorou demais. Refine os filtros e tente de novo"})
    return JSONResponse(status_code=503, content={"detail": "Banco de dados indisponível"})


@app.exception_handler(SemConexaoLivre)
def pool_esgotado(request: Request, erro: SemConexaoLivre):
    # todas as conexões do pool ocupadas por DB_ESPERA_CONEXAO segundos: melhor avisar que enfileirar sem fim
    return JSONResponse(status_code=503, content={"detail": "Servidor ocupado. Tente de novo em instantes"})
