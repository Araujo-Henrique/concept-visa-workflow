"""Verificações de saúde, para quem cuida do servidor (Docker, Nginx, monitoramento). Rotas públicas: não
mostram nenhum dado, só se a API está de pé e se consegue falar com o banco.

  - /saude  ("estou vivo?"): responde sem tocar no banco. Se falhar, o processo travou e deve ser reiniciado.
  - /pronto ("posso receber pedidos?"): confere o banco. Se falhar, o processo está vivo mas não serve:
    o balanceador tira a API da rotação, e reiniciar não ajudaria (o problema é o banco).

Separar os dois evita um erro comum: reiniciar a API à toa só porque o banco caiu por um minuto.
"""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import db

router = APIRouter(tags=["Saúde"])
registro = logging.getLogger("concept.saude")

# Quem pergunta (Docker, monitor) faz isso a cada poucos segundos: não conta no limite por IP e não enche o log.
CAMINHOS = ("/saude", "/pronto")


@router.get("/saude")
def vivo():
    return {"status": "ok"}


@router.get("/pronto")
def pronto():
    try:
        with db.Session() as sessao:
            sessao.execute(text("SET LOCAL statement_timeout = '2s'"))  # não prende quem pergunta
            sessao.execute(text("SELECT 1"))
    except Exception:
        # o motivo (endereço do banco, usuário...) fica no log; quem pergunta recebe só "indisponível"
        registro.exception("banco indisponivel na verificacao de prontidao")
        return JSONResponse(status_code=503, content={"status": "indisponivel"})
    return {"status": "ok"}
