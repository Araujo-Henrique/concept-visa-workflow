"""Regras do fluxo de situações de um processo.

Fica num serviço (e não dentro da rota) porque a mesma regra vai servir a outras entradas:
a API hoje, a importação dos dados antigos e as integrações do Projeto 3 depois.
"""
from sqlalchemy.orm import Session

from app.enums import SITUACOES, TipoEvento, TipoProcesso
from app.models import Evento, Processo

SITUACAO_FINAL = "Concluido"


class ErroDeRegra(Exception):
    """Violação de regra de negócio. A rota traduz em resposta HTTP (`status`)."""

    def __init__(self, mensagem: str, status: int = 422):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status


def mudar_situacao(sessao: Session, processo_id: int, nova: str, motivo: str | None = None,
                   usuario_id: int | None = None) -> Processo:
    """Muda a situação e registra o evento, na mesma transação (o commit é de quem chamou).

    Regras:
      - a situação precisa existir para o tipo do processo;
      - sair de Concluído exige motivo (o processo foi reaberto); a mudança vira o evento `reaberto`;
      - voltar de Concluído para Processando NÃO é bloqueado: uma negativa seguida de nova tentativa é normal.
    """
    # FOR UPDATE: trava a linha até o commit. Duas mudanças simultâneas viram uma fila, e cada uma
    # enxerga a situação já alterada pela anterior, então o histórico não registra uma "anterior" errada.
    processo = sessao.get(Processo, processo_id, with_for_update=True)
    if processo is None:
        raise ErroDeRegra("Processo não encontrado", status=404)

    if nova not in SITUACOES[TipoProcesso(processo.tipo)]:
        raise ErroDeRegra(f"Situação inválida para {processo.tipo}: use uma de {SITUACOES[TipoProcesso(processo.tipo)]}")
    anterior = processo.situacao
    if nova == anterior:
        raise ErroDeRegra(f"O processo já está em '{anterior}'", status=409)

    reabertura = anterior == SITUACAO_FINAL
    if reabertura and not (motivo and motivo.strip()):
        raise ErroDeRegra("Informe o motivo para reabrir um processo concluído")

    processo.situacao = nova
    processo.eventos.append(Evento(
        tipo=TipoEvento.REABERTO if reabertura else TipoEvento.SITUACAO_ALTERADA,
        situacao_anterior=anterior, situacao_nova=nova,
        motivo=motivo.strip() if motivo else None, usuario_id=usuario_id))
    return processo
