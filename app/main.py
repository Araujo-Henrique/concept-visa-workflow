import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg.errors import ForeignKeyViolation, QueryCanceled, UniqueViolation
from sqlalchemy.exc import DataError, IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as SemConexaoLivre

from app import db, deps, limites, logs, seguranca
from app.limite_de_corpo import LimiteDeCorpo
from app.routers import (auditoria, auth, clientes, painel, processos, referencias, saude, solicitantes, usuarios,
                         workflow)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    # liga a sessão ao banco ao subir o servidor; nos testes ela já vem ligada ao banco de teste
    seguranca.validar_segredo(os.environ.get("JWT_SECRET", ""))  # segredo fraco ou de exemplo: a API nem sobe
    if db.Session.kw.get("bind") is None:
        db.configurar()
    yield


def _docs_ligados() -> bool:
    # Desligado por padrão: o /docs e o /openapi.json são o mapa completo da API e não devem ficar à vista sem
    # querer em produção. Em desenvolvimento, API_DOCS=true no .env.
    return os.environ.get("API_DOCS", "false").strip().lower() in ("true", "1", "sim")


logs.configurar()
registro = logging.getLogger("concept.api")

_docs = _docs_ligados()
app = FastAPI(title="Concept Visa Workflow", lifespan=ciclo_de_vida, docs_url="/docs" if _docs else None,
              redoc_url="/redoc" if _docs else None, openapi_url="/openapi.json" if _docs else None)

LIMITE_CORPO_BYTES = int(os.environ.get("LIMITE_CORPO_KB", "1024")) * 1024
# Conta os bytes que chegam (o cabeçalho Content-Length sozinho não vale para corpo "chunked"). Declarado antes dos
# middlewares abaixo para ficar POR DENTRO deles: o 413 passa pelo log e leva o X-Request-ID.
app.add_middleware(LimiteDeCorpo, limite=LIMITE_CORPO_BYTES)


@app.middleware("http")
async def proteger(request: Request, chamar):
    """Antes de qualquer rota (e de qualquer consulta ao banco):
      - corpo grande demais: 413 (nenhuma tela manda mais que alguns KB; isso só serve para entupir o servidor);
      - requisições demais do mesmo IP no último minuto: 429 com Retry-After."""
    tamanho = request.headers.get("content-length")
    if tamanho is not None and (not tamanho.isdigit() or int(tamanho) > LIMITE_CORPO_BYTES):
        return JSONResponse(status_code=413, content={"detail": "Dados grandes demais"})
    if request.url.path in saude.CAMINHOS:  # monitoramento: sem limite por IP (ele pergunta o tempo todo)
        return await chamar(request)
    if espera := limites.geral.registrar(limites.ip_do_cliente(request)):
        return JSONResponse(status_code=429, headers={"Retry-After": str(espera)},
                            content={"detail": limites.mensagem_de_espera(espera)})
    return await chamar(request)


@app.middleware("http")
async def registrar_requisicao(request: Request, chamar):
    """A camada de fora (declarada por último): dá um id a cada requisição, devolve esse id no cabeçalho
    X-Request-ID e escreve uma linha no log com o resultado. Erro não tratado vira 500 com o id, e o
    traceback vai para o log (a pessoa vê só o código; o detalhe técnico nunca sai da API)."""
    id_req = logs.novo_id(request.headers.get("x-request-id"))
    logs.id_da_requisicao.set(id_req)
    inicio = time.perf_counter()
    try:
        resposta = await chamar(request)
    except Exception:
        registro.exception("erro nao tratado em %s %s", request.method, request.url.path)
        resposta = JSONResponse(status_code=500, content={"detail": "Erro interno. Informe o código ao suporte",
                                                          "id": id_req})
    resposta.headers["X-Request-ID"] = id_req
    if resposta.status_code >= 500:
        nivel = logging.ERROR
    elif resposta.status_code >= 400:
        nivel = logging.WARNING
    elif request.url.path in saude.CAMINHOS:
        nivel = logging.DEBUG  # o monitor pergunta a cada poucos segundos: não polui o log
    else:
        nivel = logging.INFO
    registro.log(nivel, "requisicao", extra={"campos": {
        "metodo": request.method, "caminho": request.url.path, "status": resposta.status_code,
        "ms": round((time.perf_counter() - inicio) * 1000, 1),
        "usuario": getattr(request.state, "usuario_id", None), "ip": limites.ip_do_cliente(request)}})
    return resposta


app.include_router(saude.router)  # saúde: pública, não mostra dado nenhum
app.include_router(auth.router)  # login e "quem sou eu": o login é a única rota pública

# Todas as demais exigem login E a permissão do método (GET lê, POST/PATCH escrevem, DELETE apaga).
# Declarar aqui, e não rota a rota, evita esquecer alguma: uma rota nova já nasce protegida.
protegidas = [Depends(deps.autorizar)]
for roteador in (clientes.router, processos.router_obt, processos.router_ren, processos.router_pass,
                 solicitantes.router, workflow.router, painel.router, referencias.router):
    app.include_router(roteador, dependencies=protegidas)
app.include_router(auditoria.router)  # auditoria: exige `administrar` (só admin)
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


@app.exception_handler(DataError)
def valor_invalido_para_o_campo(request: Request, erro: DataError):
    # Valor grande demais ou de tipo errado para a coluna. As telas e os esquemas já barram isso; se algo escapar, a
    # resposta é 422 sem repetir o valor, e o log registra só o aviso (o engine não imprime parâmetros).
    registro.warning("valor invalido para o campo em %s %s", request.method, request.url.path)
    return JSONResponse(status_code=422, content={"detail": "Um dos valores é inválido ou grande demais para o campo"})
