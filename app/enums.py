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
    """Na ordem do caminho: as opções vão para o cliente, ele decide entre a Opt A e a orientação padrão;
    a padrão é agendada (com data) e, feita, fica Fornecidas."""
    PENDENTE = "Pendente"
    OPCOES_ENVIADAS = "Opções enviadas"  # recebeu as opções e ainda não respondeu
    DECIDINDO = "Decidindo"  # escolhendo entre a Opt A e a orientação padrão
    OPTA = "Opt A"
    ESCOLHEU_PADRAO = "Escolheu padrão"  # quer a orientação padrão, ainda sem data
    AGENDADA = "Agendada"
    FORNECIDAS = "Fornecidas"


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
