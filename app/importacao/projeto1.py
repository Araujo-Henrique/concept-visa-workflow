"""Importação do banco do Projeto 1 (Concept Client Registry) para o esquema deste projeto.

O código não contém dado nenhum: recebe uma conexão de leitura com o banco antigo e uma sessão do banco
novo. Quem decide quais bancos usar (o de testes, o anonimizado ou o real) é o `.env` de cada máquina.

Tudo roda na sessão recebida e NÃO faz commit: quem chama decide gravar (importação) ou desfazer (simulação).

Mapeamento (o que muda de um esquema para o outro):
  clientes                    -> clientes
  processos_obt/ren           -> processos + processo_obt/processo_ren
  passaportes                 -> processos + processo_pass
  n_solicitantes              -> N linhas em solicitantes (o titular leva o nome do cliente)
  codigo_ds160 (linhas)       -> formularios_ds160, ligados ao solicitante pelo primeiro nome
  resultado, status_ds        -> copiados para todos os solicitantes / formulários do processo
  notas_ds160                 -> processos.observacao
  funcionarios                -> usuarios, os listados num CSV local (o e-mail não existe no banco antigo).
                                 Inativos entram com ativo=false: preservam o histórico, mas não têm acesso.
  consulado 'N/D'             -> consulado vazio
O histórico de situações do banco antigo não existe: cada processo recebe um evento "criado" na situação atual.
"""
import csv
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from psycopg import Connection
from psycopg.rows import dict_row
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import (Consulado, DocsREN, Monitoramento, Orientacao, Rascunho, Resultado, StatusDS,
                       TipoEvento)
from app.models import (Cliente, Evento, FormularioDS160, Perfil, ProcessoOBT, ProcessoPASS, ProcessoREN,
                        Solicitante, Usuario)

# AA00 + 6 alfanuméricos, depois (opcional) " - nome" ou " - novo"
LINHA_CODIGO = re.compile(r"^\s*(AA00[A-Z0-9]{6})(?![A-Z0-9])\s*(?:[-–—]\s*(.*?))?\s*$", re.IGNORECASE)
MAX_AVISOS = 50


@dataclass
class Relatorio:
    origem: dict[str, int] = field(default_factory=dict)
    destino: dict[str, int] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    n_avisos: int = 0

    def avisar(self, mensagem: str):
        self.n_avisos += 1
        if len(self.avisos) < MAX_AVISOS:
            self.avisos.append(mensagem)

    def confere(self) -> bool:
        """Todos os registros da origem chegaram ao destino? (solicitantes e formulários podem diferir: ver avisos)"""
        return all(self.origem[k] == self.destino[k] for k in ("clientes", "processos_obt", "processos_ren", "passaportes"))


# ---------------------------------------------------------------- funções puras (testáveis sem banco)

def chave(nome: str) -> str:
    """Primeiro nome sem acento e em minúsculas: 'José Silva' e 'jose' dão a mesma chave."""
    primeiro = (nome.split() or [""])[0]
    sem_acento = unicodedata.normalize("NFKD", primeiro).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def ler_codigos(texto: str | None) -> tuple[list[tuple[str, str | None]], list[str]]:
    """Separa as linhas do campo codigo_ds160 em [(codigo, primeiro_nome_ou_None)] e linhas fora do padrão.

    `AA00... - Maria` abre uma pessoa; `AA00... - novo` é um formulário refeito, da mesma pessoa da linha
    anterior (por isso o nome fica None quando ainda não houve nenhuma pessoa)."""
    codigos, fora = [], []
    pessoa = None
    for linha in (texto or "").splitlines():
        if not linha.strip():
            continue
        achou = LINHA_CODIGO.match(linha)
        if not achou:
            fora.append(linha.strip())
            continue
        nome = (achou.group(2) or "").strip()
        if nome and nome.lower() != "novo":
            pessoa = nome.split()[0]
        codigos.append((achou.group(1).upper(), pessoa))
    return codigos, fora


def montar_solicitantes(cliente_nome: str, n: int, codigos: list[tuple[str, str | None]]):
    """Cria os solicitantes do processo e devolve (lista, função que acha o solicitante de um código).

    O titular tem o nome do cliente; os demais começam como 'Solicitante 2', 3... e ganham o primeiro nome
    que aparece nos códigos, na ordem. Se os códigos citam mais pessoas que n_solicitantes, criamos as que faltam."""
    titular = Solicitante(nome=cliente_nome, titular=True)
    extras = [Solicitante(nome=f"Solicitante {i}") for i in range(2, max(n, 1) + 1)]
    todos = [titular, *extras]
    livres = list(extras)
    por_chave: dict[str, Solicitante] = {}
    excedente = False
    for _, pessoa in codigos:
        if pessoa is None:
            continue
        k = chave(pessoa)
        if k in por_chave:
            continue
        if k == chave(cliente_nome) and titular not in por_chave.values():
            por_chave[k] = titular
        elif livres:
            extra = livres.pop(0)
            extra.nome = pessoa
            por_chave[k] = extra
        else:
            novo = Solicitante(nome=pessoa)
            todos.append(novo)
            por_chave[k] = novo
            excedente = True

    def de_quem(pessoa: str | None) -> Solicitante:
        return por_chave.get(chave(pessoa), titular) if pessoa else titular

    return todos, de_quem, excedente


def carregar_usuarios_csv(caminho: str | Path) -> dict[str, tuple[str, str]]:
    """CSV local (fora do Git) com `nome;email;perfil`. Devolve {nome do funcionário em minúsculas: (email, perfil)}."""
    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        return {linha["nome"].strip().lower(): (linha["email"].strip(), (linha.get("perfil") or "atendente").strip())
                for linha in csv.DictReader(arquivo, delimiter=";")}


# ---------------------------------------------------------------- leitura da origem

class Origem:
    """Leitura do banco antigo. Tolera o banco sem as colunas do DS-160 (versões anteriores do Projeto 1)."""

    def __init__(self, conexao: Connection):
        self.cur = conexao.cursor(row_factory=dict_row)

    def tem_coluna(self, tabela: str, coluna: str) -> bool:
        self.cur.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() "
            "AND table_name = %s AND column_name = %s", [tabela, coluna])
        return self.cur.fetchone() is not None

    def todos(self, tabela: str) -> list[dict]:
        self.cur.execute(f"SELECT * FROM {tabela} ORDER BY id")  # nome de tabela fixo no nosso código
        return self.cur.fetchall()


# ---------------------------------------------------------------- importação

def _observacao(notas: str | None, extras: list[str]) -> str | None:
    partes = [p for p in [(notas or "").strip(), *extras] if p]
    return "\n".join(partes) or None


def importar(conexao_origem: Connection, sessao: Session, usuarios_csv: dict | None = None) -> Relatorio:
    relatorio = Relatorio()
    origem = Origem(conexao_origem)

    if sessao.scalar(select(func.count()).select_from(Cliente)) or \
            sessao.scalar(select(func.count()).select_from(ProcessoOBT)):
        raise RuntimeError("O banco de destino já tem dados: a importação é para um banco novo (só migrations).")

    perfis = {p.nome: p.id for p in sessao.scalars(select(Perfil))}

    # ---- funcionários -> usuários (só os que estão no CSV)
    usuario_por_funcionario: dict[int, int] = {}
    nome_do_funcionario: dict[int, str] = {}
    for f in origem.todos("funcionarios"):
        nome_do_funcionario[f["id"]] = f["nome"]
        dados = (usuarios_csv or {}).get(f["nome"].strip().lower())
        if dados is None:
            continue
        email, perfil = dados
        if perfil not in perfis:
            raise ValueError(f"Perfil '{perfil}' do CSV não existe (use {sorted(perfis)})")
        usuario = Usuario(nome=f["nome"], email=email, perfil_id=perfis[perfil], ativo=f["ativo"])
        sessao.add(usuario)
        sessao.flush()
        usuario_por_funcionario[f["id"]] = usuario.id

    # ---- clientes
    cliente_novo: dict[int, Cliente] = {}
    for c in origem.todos("clientes"):
        cliente = Cliente(nome=c["nome"], email=c["email"], telefone=c["telefone"], grupo=c["grupo"])
        sessao.add(cliente)
        cliente_novo[c["id"]] = cliente
    sessao.flush()
    relatorio.origem["clientes"] = len(cliente_novo)

    codigos_usados: set[str] = set()
    esperados = {"solicitantes": 0, "formularios": 0}

    def solicitantes_e_formularios(processo, cliente: Cliente, n: int, codigo_ds160: str | None,
                                   status_ds: str | None, resultado: str | None, rotulo: str) -> list[str]:
        """Liga ao processo os solicitantes e formulários; devolve linhas extras para a observação."""
        extras_obs: list[str] = []
        codigos, fora = ler_codigos(codigo_ds160)
        for linha in fora:
            extras_obs.append(linha)
            relatorio.avisar(f"{rotulo}: linha de código fora do padrão movida para a observação: {linha[:40]!r}")
        todos, de_quem, excedente = montar_solicitantes(cliente.nome, n, codigos)
        if excedente:
            relatorio.avisar(f"{rotulo}: os códigos citam mais pessoas que n_solicitantes ({n}); solicitantes criados a mais")
        for s in todos:
            s.resultado = Resultado(resultado) if resultado else Resultado.PROCESSANDO
            processo.solicitantes.append(s)
        esperados["solicitantes"] += n
        status = StatusDS(status_ds) if status_ds else StatusDS.PENDENTE
        criados = 0
        for codigo, pessoa in codigos:
            esperados["formularios"] += 1
            if codigo in codigos_usados:
                relatorio.avisar(f"{rotulo}: código {codigo} repetido em outro processo; ignorado")
                continue
            codigos_usados.add(codigo)
            de_quem(pessoa).formularios.append(FormularioDS160(codigo=codigo, status=status))
            criados += 1
        if criados == 0 and status != StatusDS.PENDENTE:
            extras_obs.append(f"Status DS-160 (histórico): {status.value}")  # não há formulário para guardá-lo
        return extras_obs

    def grava(processo, situacao: str):
        processo.eventos.append(Evento(tipo=TipoEvento.CRIADO, situacao_nova=situacao))
        sessao.add(processo)

    # ---- processos OBT
    tem_cod = origem.tem_coluna("processos_obt", "codigo_ds160")
    tem_notas = origem.tem_coluna("processos_obt", "notas_ds160")
    obt = origem.todos("processos_obt")
    sem_usuario: Counter = Counter()  # funcionário sem usuário -> quantos processos perderam o "orientação por"
    for r in obt:
        cliente = cliente_novo[r["cliente_id"]]
        por = usuario_por_funcionario.get(r["orientacao_por_id"]) if r["orientacao_por_id"] else None
        if r["orientacao_por_id"] and por is None:
            sem_usuario[nome_do_funcionario.get(r["orientacao_por_id"], f"id {r['orientacao_por_id']}")] += 1
        processo = ProcessoOBT(
            cliente_id=cliente.id, situacao=r["situacao"],
            consulado=None if r["consulado"] == "N/D" else Consulado(r["consulado"]),
            monitoramento=Monitoramento(r["monitoramento"]),
            data_casv=r["data_casv"], data_entrevista=r["data_entrevista"],
            data_vencimento_taxa=r["data_vencimento_taxa"],
            status_rascunho=Rascunho(r["status_rascunho"]), orientacao=Orientacao(r["orientacao"]),
            orientacao_data=r["orientacao_data"], orientacao_por_id=por, codigo_rastreio=r["codigo_rastreio"])
        extras = solicitantes_e_formularios(
            processo, cliente, r["n_solicitantes"], r["codigo_ds160"] if tem_cod else None,
            r["status_ds"], r["resultado"], f"OBT {r['id']}")
        processo.observacao = _observacao(r["notas_ds160"] if tem_notas else None, extras)
        grava(processo, r["situacao"])
    if sem_usuario:
        detalhe = ", ".join(f"{nome} ({n})" for nome, n in sem_usuario.most_common())
        relatorio.avisar(f"{sum(sem_usuario.values())} processos OBT tinham 'orientação por' de funcionários sem "
                         f"usuário no CSV; o campo ficou vazio. Inclua-os no CSV (inativos entram sem acesso): {detalhe}")
    relatorio.origem["processos_obt"] = len(obt)

    # ---- processos REN
    tem_cod = origem.tem_coluna("processos_ren", "codigo_ds160")
    tem_notas = origem.tem_coluna("processos_ren", "notas_ds160")
    ren = origem.todos("processos_ren")
    for r in ren:
        cliente = cliente_novo[r["cliente_id"]]
        processo = ProcessoREN(
            cliente_id=cliente.id, situacao=r["situacao"], consulado=Consulado(r["consulado"]),
            data_casv=r["data_casv"], docs=DocsREN(r["docs"]), status_rascunho=Rascunho(r["status_rascunho"]),
            endereco=r["endereco"], codigo_rastreio=r["codigo_rastreio"])
        extras = solicitantes_e_formularios(
            processo, cliente, r["n_solicitantes"], r["codigo_ds160"] if tem_cod else None,
            r["status_ds"], None, f"REN {r['id']}")
        processo.observacao = _observacao(r["notas_ds160"] if tem_notas else None, extras)
        grava(processo, r["situacao"])
    relatorio.origem["processos_ren"] = len(ren)

    # ---- passaportes
    pas = origem.todos("passaportes")
    for r in pas:
        cliente = cliente_novo[r["cliente_id"]]
        situacao = r["situacao"] or "Pendente"  # no banco antigo a situação do passaporte podia ser vazia
        if not r["situacao"]:
            relatorio.avisar(f"PASS {r['id']}: sem situação; importado como 'Pendente'")
        processo = ProcessoPASS(cliente_id=cliente.id, situacao=situacao, data_pf=r["data_pf"],
                                prazo_pf=r["prazo_pf"])
        solicitantes_e_formularios(processo, cliente, r["n_solicitantes"], None, None, None, f"PASS {r['id']}")
        grava(processo, situacao)
    relatorio.origem["passaportes"] = len(pas)

    sessao.flush()

    # ---- conferência: origem x destino
    conta = lambda modelo: sessao.scalar(select(func.count()).select_from(modelo))
    relatorio.destino = {
        "clientes": conta(Cliente), "processos_obt": conta(ProcessoOBT),
        "processos_ren": conta(ProcessoREN), "passaportes": conta(ProcessoPASS)}
    relatorio.origem["solicitantes (esperados)"] = esperados["solicitantes"]
    relatorio.destino["solicitantes (esperados)"] = conta(Solicitante)
    relatorio.origem["formularios ds160 (linhas de código)"] = esperados["formularios"]
    relatorio.destino["formularios ds160 (linhas de código)"] = conta(FormularioDS160)
    relatorio.origem["usuarios (do CSV)"] = len(usuario_por_funcionario)
    relatorio.destino["usuarios (do CSV)"] = conta(Usuario)
    return relatorio
