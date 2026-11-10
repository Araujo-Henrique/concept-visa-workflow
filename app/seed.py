"""Dados FICTÍCIOS para a máquina de testes e para demonstrações.

Tudo é inventado: nomes sorteados de listas, e-mails `@exemplo.com`, telefones sem dono, códigos DS-160
aleatórios. A semente é fixa, então o mesmo comando gera sempre o mesmo conjunto (bom para tutoriais e testes).

Recusa rodar num banco que já tenha clientes: assim o seed nunca se mistura com dados reais.
O que ele cria passa pelas mesmas regras da aplicação (o histórico de cada processo vem de `mudar_situacao`).
"""
import random
import unicodedata
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import auditoria
from app.enums import (SITUACOES, Consulado, DocsREN, Orientacao, Rascunho, Resultado, StatusDS, TipoEvento,
                       TipoProcesso)
from app.models import (Cliente, Evento, FormularioDS160, Processo, ProcessoOBT, ProcessoPASS, ProcessoREN,
                        Solicitante, Usuario)
from app.servicos.usuarios import achar_por_email, criar_usuario
from app.servicos.workflow import SITUACAO_FINAL, mudar_situacao

NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gabriela", "Hugo", "Iara", "João", "Karen",
         "Lucas", "Marina", "Nelson", "Olívia", "Paulo", "Rafaela", "Sérgio", "Tatiana", "Vinícius"]
SOBRENOMES = ["Almeida", "Barros", "Cardoso", "Duarte", "Esteves", "Ferraz", "Guedes", "Holanda", "Ibiapina",
              "Junqueira", "Klein", "Lacerda", "Moura", "Nogueira", "Ornelas", "Pacheco", "Quintela", "Rangel",
              "Siqueira", "Tavares"]

# (nome, e-mail, perfil, ativo): um de cada perfil e um ex-funcionário, para mostrar o "ativo = false"
USUARIOS_DEMO = [
    ("Admin Demo", "admin@exemplo.com", "admin", True),
    ("Atendente Demo", "atendente@exemplo.com", "atendente", True),
    ("Leitor Demo", "leitor@exemplo.com", "leitor", True),
    ("Ex-Funcionario Demo", "ex-funcionario@exemplo.com", "leitor", False),
]

_ALFABETO_DS160 = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_MOTIVO_REABERTURA = "Cliente pediu revisao dos dados"


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return ".".join(sem_acento.lower().split())


def gerar_nomes(rng: random.Random, quantidade: int) -> list[str]:
    """Nomes únicos, na ordem em que foram sorteados (um `set` embaralharia a ordem de uma execução para outra)."""
    nomes: list[str] = []
    vistos: set[str] = set()
    while len(nomes) < quantidade:
        nome = f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)} {rng.choice(SOBRENOMES)}"
        if nome.lower() not in vistos:
            vistos.add(nome.lower())
            nomes.append(nome)
    return nomes


class _Gerador:
    """Guarda o sorteio, a data de referência e os códigos DS-160 já usados (cada código é único)."""

    def __init__(self, rng: random.Random, hoje: date, atendente: Usuario):
        self.rng, self.hoje, self.atendente = rng, hoje, atendente
        self.codigos: set[str] = set()

    def dia(self, de: int, ate: int) -> date:
        return self.hoje + timedelta(days=self.rng.randint(de, ate))

    def codigo_ds160(self) -> str:
        while True:
            codigo = "AA00" + "".join(self.rng.choices(_ALFABETO_DS160, k=6))
            if codigo not in self.codigos:
                self.codigos.add(codigo)
                return codigo

    def detalhes(self, tipo: TipoProcesso, final: str) -> dict:
        """Campos próprios de cada tipo, coerentes entre si (data de CASV sempre vem com consulado)."""
        rng = self.rng
        avancado = final in ("Pago", "Entrevista", SITUACAO_FINAL)
        if tipo is TipoProcesso.PASS:
            if final in ("Pago", "Processando", SITUACAO_FINAL):
                data_pf = self.dia(-20, 40)
                return {"data_pf": data_pf, "prazo_pf": data_pf + timedelta(days=30)}
            return {}

        consulado = rng.choice(list(Consulado)) if avancado or rng.random() < 0.7 else None
        if tipo is TipoProcesso.REN:
            d = {"consulado": consulado, "docs": rng.choice(list(DocsREN)),
                 "status_rascunho": rng.choice(list(Rascunho)),
                 "endereco": f"Rua Exemplo {rng.randint(1, 999)}, Curitiba/PR"}
            if avancado:
                d["data_casv"] = self.dia(-30, 60)
            if final == SITUACAO_FINAL:
                d["codigo_rastreio"] = f"BR{rng.randint(10**8, 10**9 - 1)}XX"
            return d

        orientacao = rng.choice(list(Orientacao))
        d = {"consulado": consulado, "status_rascunho": rng.choice(list(Rascunho)), "orientacao": orientacao}
        if orientacao is Orientacao.AGENDADA:
            d.update(orientacao_data=self.dia(-10, 20), orientacao_por_id=self.atendente.id)
        elif orientacao is Orientacao.FORNECIDAS:
            d["orientacao_por_id"] = self.atendente.id
        if avancado:
            d["data_casv"] = self.dia(-30, 60)
            if rng.random() < 0.5:
                d["data_entrevista"] = d["data_casv"] + timedelta(days=1)
        else:
            d["data_vencimento_taxa"] = self.dia(5, 90)
        return d

    def situacao_final(self, tipo: TipoProcesso) -> str:
        lista = SITUACOES[tipo]
        return self.rng.choice(lista + [SITUACAO_FINAL] * 2)  # Concluído pesa mais, como na realidade

    def processo(self, sessao: Session, cliente: Cliente, tipo: TipoProcesso, final: str, *,
                 anterior_id: int | None = None, resultado: Resultado | None = None,
                 reabrir: bool = False) -> Processo:
        rng = self.rng
        lista = SITUACOES[tipo]
        ate = lista.index(final)
        passos = [s for s in lista[1:ate] if rng.random() < 0.6] + ([final] if ate > 0 else [])

        modelo = {TipoProcesso.OBT: ProcessoOBT, TipoProcesso.REN: ProcessoREN, TipoProcesso.PASS: ProcessoPASS}[tipo]
        processo = modelo(cliente_id=cliente.id, situacao=lista[0], processo_anterior_id=anterior_id,
                          criado_por_id=self.atendente.id, **self.detalhes(tipo, final))
        processo.solicitantes.append(Solicitante(nome=cliente.nome, titular=True))
        if tipo is not TipoProcesso.PASS:
            for _ in range(rng.choice([0, 0, 1, 2, 3])):  # a família que viaja junto
                processo.solicitantes.append(Solicitante(nome=f"{rng.choice(NOMES)} {cliente.nome.split()[-1]}"))
        processo.eventos.append(Evento(tipo=TipoEvento.CRIADO, situacao_nova=lista[0], usuario_id=self.atendente.id))
        sessao.add(processo)
        sessao.flush()

        # o histórico vem do mesmo serviço da API: cada passo grava o evento certo
        for passo in passos:
            mudar_situacao(sessao, processo.id, passo, usuario_id=self.atendente.id)
        if reabrir:
            mudar_situacao(sessao, processo.id, "Processando", motivo=_MOTIVO_REABERTURA,
                           usuario_id=self.atendente.id)

        concluido = final == SITUACAO_FINAL and not reabrir
        for pessoa in processo.solicitantes:
            if resultado is not None:
                pessoa.resultado = resultado
            elif concluido:
                pessoa.resultado = Resultado.APROVADO if rng.random() < 0.85 else Resultado.NEGADO
            if tipo is not TipoProcesso.PASS and rng.random() < 0.8:
                pessoa.formularios.append(FormularioDS160(
                    codigo=self.codigo_ds160(),
                    status=StatusDS.FECHADO if concluido else rng.choice(list(StatusDS))))
        sessao.flush()
        return processo


def semear(sessao: Session, senha: str | None, *, quantidade: int = 36, semente: int = 42,
           hoje: date | None = None, aceitar_usuarios_existentes: bool = False) -> dict[str, int]:
    """Cria usuários demo, clientes e processos fictícios. O commit é de quem chama.

    `senha` vale só para o usuário demo admin (só admin entra com senha; os outros perfis entram com o Google).
    None = sem senha para todos.
    """
    if sessao.scalar(select(func.count()).select_from(Cliente)):
        raise RuntimeError("O banco já tem clientes: o seed só roda num banco sem clientes, "
                           "para nunca misturar dados fictícios com dados reais.")
    if not aceitar_usuarios_existentes:
        demo = {email.lower() for _, email, _, _ in USUARIOS_DEMO}
        outros = [e for e in sessao.scalars(select(Usuario.email)) if e.lower() not in demo]
        if outros:
            raise RuntimeError(f"O banco já tem {len(outros)} usuário(s) que não são do seed: provavelmente é um banco "
                               "de verdade. Se é só o seu administrador de desenvolvimento, use --aceito-usuarios-existentes.")
    auditoria.identificar(sessao, origem="seed")  # na auditoria, o que o seed criou fica marcado como seed
    rng = random.Random(semente)

    usuarios: dict[str, Usuario] = {}
    for nome, email, perfil, ativo in USUARIOS_DEMO:
        usuario = achar_por_email(sessao, email)
        if usuario is None:
            usuario = criar_usuario(sessao, nome, email, perfil, senha if perfil == "admin" else None)
            usuario.ativo = ativo
        usuarios[perfil if ativo else "inativo"] = usuario
    gerador = _Gerador(rng, hoje or date.today(), usuarios["atendente"])

    nomes = gerar_nomes(rng, quantidade)
    for i, nome in enumerate(nomes):
        par = i // 2  # os oito primeiros formam quatro famílias (mesmo grupo)
        cliente = Cliente(nome=nome, email=f"{_slug(nome)}@exemplo.com", telefone=f"4199{rng.randint(1000000, 9999999)}",
                          grupo=f"Familia Demo {par + 1}" if i < 8 else None)
        sessao.add(cliente)
        sessao.flush()

        if i == 0:  # negativa e nova tentativa: o segundo processo aponta para o primeiro
            anterior = gerador.processo(sessao, cliente, TipoProcesso.OBT, SITUACAO_FINAL, resultado=Resultado.NEGADO)
            gerador.processo(sessao, cliente, TipoProcesso.OBT, "Processando", anterior_id=anterior.id)
        elif i == 1:  # processo concluído que foi reaberto com motivo
            gerador.processo(sessao, cliente, TipoProcesso.REN, SITUACAO_FINAL, reabrir=True)
        else:
            for _ in range(1 if rng.random() < 0.75 else 2):
                tipo = rng.choices(list(TipoProcesso), weights=[55, 30, 15])[0]
                gerador.processo(sessao, cliente, tipo, gerador.situacao_final(tipo))

    def contar(modelo) -> int:
        return sessao.scalar(select(func.count()).select_from(modelo))

    return {"usuarios": contar(Usuario), "clientes": contar(Cliente), "processos": contar(Processo),
            "solicitantes": contar(Solicitante), "formularios_ds160": contar(FormularioDS160),
            "eventos": contar(Evento)}
