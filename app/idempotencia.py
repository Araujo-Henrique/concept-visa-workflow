"""Idempotência: o mesmo pedido de criação, enviado duas vezes, vale uma vez só.

O problema: duplo clique, F5 depois de enviar, rede que cai depois do servidor gravar e o cliente reenvia.
Sem proteção, nascem dois clientes ou dois processos.

Como funciona (cabeçalho `Idempotency-Key`, opcional; o front manda um código novo por formulário):
  1. a chave é RESERVADA numa tabela (única por usuário+chave): quem reserva primeiro executa;
  2. deu certo (2xx): a resposta fica guardada e qualquer reenvio recebe a mesma resposta, sem executar de novo
     (cabeçalho `Idempotent-Replayed: true`);
  3. deu erro: a reserva é apagada. O erro não fica guardado: a pessoa corrige os dados e tenta de novo
     com a mesma chave;
  4. reenvio enquanto o primeiro ainda roda (duplo clique): espera terminar e devolve o mesmo resultado;
  5. mesma chave com dados diferentes, ou em outra rota: 422 (provavelmente é um erro de quem chamou).

Limite honesto: a resposta é guardada DEPOIS que a rota gravou. Se o servidor cair exatamente entre os dois
passos, a reserva fica sem resposta e, passados ABANDONO_SEGUNDOS, o reenvio executa de novo. A janela é de
milissegundos; as travas do banco (titular único, nome único) continuam valendo como segunda defesa.

Só entra nas rotas que usam `RotaIdempotente`. Login, troca de senha e renovação ficam de fora de propósito:
suas respostas têm token e não devem ser guardadas.
"""
import asyncio
import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from app import db, seguranca
from app.models import ChaveIdempotencia

CABECALHO = "idempotency-key"
_CHAVE_VALIDA = re.compile(r"[A-Za-z0-9._:-]{8,80}")
VALIDADE = timedelta(hours=24)
ABANDONO_SEGUNDOS = 60
registro = logging.getLogger("concept.idempotencia")


def _espera_maxima() -> float:
    try:
        return float(os.environ.get("IDEMPOTENCIA_ESPERA_SEGUNDOS", "10"))
    except ValueError:
        return 10.0


@dataclass
class _Estado:
    tipo: str  # reservada | pronta | conflito | andamento | sumiu
    status: int | None = None
    corpo: str | None = None


def _daquele_usuario(usuario_id: int, chave: str):
    return (ChaveIdempotencia.usuario_id == usuario_id, ChaveIdempotencia.chave == chave)


def _reservar(usuario_id: int, chave: str, escopo: str, impressao: str) -> _Estado:
    with db.Session() as sessao:
        vencidas = ChaveIdempotencia.criado_em < datetime.now(timezone.utc) - VALIDADE
        sessao.execute(delete(ChaveIdempotencia).where(vencidas))
        try:
            sessao.add(ChaveIdempotencia(usuario_id=usuario_id, chave=chave, escopo=escopo, impressao=impressao))
            sessao.commit()
            return _Estado("reservada")
        except IntegrityError:  # alguém (talvez o pedido anterior) já tem essa chave
            sessao.rollback()
        atual = sessao.scalar(select(ChaveIdempotencia).where(*_daquele_usuario(usuario_id, chave)))
        if atual is None:  # foi liberada neste instante: tenta reservar de novo
            return _Estado("sumiu")
        if atual.escopo != escopo or atual.impressao != impressao:
            return _Estado("conflito")
        if atual.status is not None:
            return _Estado("pronta", atual.status, atual.corpo)
        if datetime.now(timezone.utc) - atual.criado_em > timedelta(seconds=ABANDONO_SEGUNDOS):
            sessao.delete(atual)  # o servidor caiu no meio: a reserva ficou órfã
            sessao.commit()
            return _Estado("sumiu")
        return _Estado("andamento")


def _guardar(usuario_id: int, chave: str, status: int, corpo: str) -> None:
    with db.Session() as sessao:
        linha = sessao.scalar(select(ChaveIdempotencia).where(*_daquele_usuario(usuario_id, chave)))
        if linha is not None:
            linha.status, linha.corpo = status, corpo
            sessao.commit()


def _liberar(usuario_id: int, chave: str) -> None:
    with db.Session() as sessao:
        sessao.execute(delete(ChaveIdempotencia).where(*_daquele_usuario(usuario_id, chave)))
        sessao.commit()


def _usuario_do_token(request: Request) -> int | None:
    esquema, _, token = request.headers.get("authorization", "").partition(" ")
    return seguranca.ler_token(token) if esquema.lower() == "bearer" and token else None


def _repetir(estado: _Estado) -> Response:
    conteudo = estado.corpo or ""
    resposta = Response(content=conteudo, status_code=estado.status or 200,
                        media_type="application/json" if conteudo else None)
    resposta.headers["Idempotent-Replayed"] = "true"
    return resposta


class RotaIdempotente(APIRoute):
    """Rota que respeita o `Idempotency-Key` nos POST. Sem o cabeçalho, nada muda."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def tratar(request: Request) -> Response:
            chave = request.headers.get(CABECALHO)
            if request.method != "POST" or chave is None:
                return await original(request)
            if not _CHAVE_VALIDA.fullmatch(chave):
                return JSONResponse(status_code=422, content={
                    "detail": "Idempotency-Key inválida: use de 8 a 80 caracteres (letras, números, . _ : -)"})
            usuario_id = _usuario_do_token(request)
            if usuario_id is None:  # sem login válido: a rota responde 401 como sempre
                return await original(request)

            impressao = hashlib.sha256(await request.body()).hexdigest()
            escopo = f"{request.method} {request.url.path}"
            limite = time.monotonic() + _espera_maxima()
            while True:
                estado = await run_in_threadpool(_reservar, usuario_id, chave, escopo, impressao)
                if estado.tipo == "reservada":
                    break
                if estado.tipo == "pronta":
                    registro.info("pedido repetido: devolvida a resposta guardada (%s)", escopo)
                    return _repetir(estado)
                if estado.tipo == "conflito":
                    return JSONResponse(status_code=422, content={
                        "detail": "Esta Idempotency-Key já foi usada em outro pedido (dados ou rota diferentes)"})
                if estado.tipo == "andamento":
                    if time.monotonic() > limite:
                        return JSONResponse(status_code=409, headers={"Retry-After": "2"}, content={
                            "detail": "Este pedido ainda está sendo processado. Aguarde um instante"})
                    await asyncio.sleep(0.2)

            try:
                resposta = await original(request)
            except BaseException:
                await run_in_threadpool(_liberar, usuario_id, chave)  # erro: a chave fica livre para nova tentativa
                raise
            try:
                if 200 <= resposta.status_code < 300:
                    await run_in_threadpool(_guardar, usuario_id, chave, resposta.status_code,
                                            bytes(resposta.body).decode("utf-8"))
                else:
                    await run_in_threadpool(_liberar, usuario_id, chave)
            except Exception:
                # a rota já gravou: a pessoa recebe a resposta mesmo assim (a reserva órfã expira sozinha)
                registro.exception("nao consegui guardar a resposta da chave de idempotencia")
            return resposta

        return tratar
