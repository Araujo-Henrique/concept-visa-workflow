from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.deps import Sessao, UsuarioAtual
from app.models import Evento, Processo
from app.routers.comum import obter_ou_404
from app.schemas.workflow import EventoOut, MudarSituacao
from app.servicos.workflow import ErroDeRegra, mudar_situacao

router = APIRouter(prefix="/processos", tags=["Workflow"])


@router.post("/{processo_id}/situacao", response_model=EventoOut)
def mudar(processo_id: int, dados: MudarSituacao, sessao: Sessao, usuario: UsuarioAtual):
    """Muda a situação do processo e devolve o evento criado. Vale para OBT, REN e PASS."""
    try:
        processo = mudar_situacao(sessao, processo_id, dados.situacao, dados.motivo, usuario_id=usuario.id)
    except ErroDeRegra as erro:
        raise HTTPException(status_code=erro.status, detail=erro.mensagem)
    sessao.commit()
    return EventoOut.model_validate(processo.eventos[-1])


@router.get("/{processo_id}/eventos", response_model=list[EventoOut])
def historico(processo_id: int, sessao: Sessao):
    """Linha do tempo do processo, do mais antigo ao mais recente."""
    obter_ou_404(sessao, Processo, processo_id, "Processo")
    eventos = sessao.scalars(select(Evento).where(Evento.processo_id == processo_id).order_by(Evento.id))
    return [EventoOut.model_validate(e) for e in eventos]
