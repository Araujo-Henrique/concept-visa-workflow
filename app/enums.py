from enum import Enum


class TipoProcesso(str, Enum):
    OBT = "OBT"
    REN = "REN"
    PASS = "PASS"


class Consulado(str, Enum):
    POA = "POA"
    RIO = "RIO"
    BSB = "BSB"
    SP = "SP"
    REC = "REC"


class Rascunho(str, Enum):
    PENDENTE = "Pendente"
    PARCIAL = "Parcial"
    ENVIADO = "Enviado"


class StatusDS(str, Enum):
    PENDENTE = "Pendente"
    PARCIAL = "Parcial"
    ABERTO = "Aberto"
    PREENCHIDO = "Preenchido"
    REVISADO = "Revisado"
    FECHADO = "Fechado"


class Resultado(str, Enum):
    PROCESSANDO = "Processando"
    APROVADO = "Aprovado"
    NEGADO = "Negado"


class Orientacao(str, Enum):
    OPTA = "Opt A"
    FORNECIDAS = "Fornecidas"
    AGENDADA = "Agendada"
    PENDENTE = "Pendente"


class Monitoramento(str, Enum):
    ATIVO = "Ativo"
    CONCLUIDO = "Concluido"


class DocsREN(str, Enum):
    PENDENTE = "Pendente"
    PARCIAL = "Parcial"
    ENTREGUE = "Entregue"


class TipoEvento(str, Enum):
    CRIADO = "criado"
    SITUACAO_ALTERADA = "situacao_alterada"
    REABERTO = "reaberto"  # saiu de Concluido: exige motivo


# Situações válidas por tipo de processo. Viram linhas da tabela `situacoes` na migration base;
# o banco, e não o código, decide quais situações existem (FK composta em processos).
SITUACOES: dict[TipoProcesso, list[str]] = {
    TipoProcesso.OBT: ["Pagamento Pendente", "Boleto", "Credito", "Limbo", "Processando",
                       "Cadastro", "Administrativo", "Pago", "Concluido"],
    TipoProcesso.REN: ["Pagamento Pendente", "Boleto", "Credito", "Limbo", "Processando",
                       "Cadastro", "Administrativo", "Entrevista", "Concluido"],
    TipoProcesso.PASS: ["Pendente", "Pagamento Pendente", "Pago", "Boleto", "Pix",
                        "Processando", "Concluido"],
}

PERFIS = ["admin", "atendente", "leitor"]
