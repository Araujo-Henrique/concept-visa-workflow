"""Importação do banco do Projeto 1 (Concept Client Registry) para o esquema deste projeto.

O código não contém dado nenhum: recebe uma conexão de leitura com o banco antigo e uma sessão do banco
novo. Quem decide quais bancos usar (o de testes, o anonimizado ou o real) é o `.env` de cada máquina.

Tudo roda na sessão recebida e NÃO faz commit: quem chama decide gravar (importação) ou desfazer (simulação).

Mapeamento (o que muda de um esquema para o outro):
  clientes                    -> clientes (com e-mail, telefone, nome e grupo padronizados)
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

Regras de padronização (decididas com o negócio):
  - n_solicitantes é a verdade: o processo tem exatamente N solicitantes. Nomes citados além de N não criam
    pessoas; os formulários deles ficam no titular e o caso vai para o relatório de exceções.
  - código DS-160 repetido: o cliente muda de REN para OBT (para cair no calendário de orientações), então o
    mesmo código aparece nos dois. O formulário fica no processo mais recente (OBT antes de REN, depois o maior
    id); o outro processo guarda uma nota na observação. Repetição entre clientes diferentes é resolvida do
    mesmo jeito, mas entra no relatório como "revisar".
  - passaporte sem situação entra como "Pendente".
  - e-mail em minúsculas e sem espaços, telefone só com dígitos (sem o 55), nome em CAIXA ALTA vira Nome Próprio,
    grupos que só diferem em caixa/espaços são unificados.
Tudo o que foi decidido por regra e merece olhar humano vai para `Relatorio.excecoes` (exportável em CSV).
"""
import csv
import re
import unicodedata
from collections import Counter, defaultdict
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

CODIGO = re.compile(r"(?<![A-Z0-9])AA00[A-Z0-9]{6}(?![A-Z0-9])", re.IGNORECASE)  # AA00 + 6 alfanuméricos
COMENTARIO = re.compile(r"\([^)]*\)")                      # (fechado), (preenchido por ele mesmo)...
NOVO = re.compile(r"^nov[oa]\b", re.IGNORECASE)               # novo, nova, nova DS: formulário refeito
NOME = re.compile(r"^[^\W\d_]+(?:-[^\W\d_]+)*$")              # uma palavra só de letras (aceita hífen)
MAX_AVISOS = 50
PARTICULAS = {"da", "de", "do", "das", "dos", "e"}
COLUNAS_EXCECOES = ("categoria", "tabela", "id_origem", "cliente_id_origem", "detalhe", "acao")


@dataclass
class Excecao:
    """Uma decisão tomada por regra que merece olhar humano. Sempre as mesmas colunas, para o CSV."""
    categoria: str
    tabela: str          # OBT, REN, PASS
    id_origem: int
    cliente_id_origem: int | None
    detalhe: str
    acao: str


@dataclass
class Relatorio:
    origem: dict[str, int] = field(default_factory=dict)
    destino: dict[str, int] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    n_avisos: int = 0
    excecoes: list[Excecao] = field(default_factory=list)
    normalizados: Counter = field(default_factory=Counter)  # correções automáticas, só contagem

    def avisar(self, mensagem: str):
        self.n_avisos += 1
        if len(self.avisos) < MAX_AVISOS:
            self.avisos.append(mensagem)

    def registrar(self, categoria: str, tabela: str, id_origem: int, cliente_id: int | None, detalhe: str, acao: str):
        self.excecoes.append(Excecao(categoria, tabela, id_origem, cliente_id, detalhe, acao))
        self.avisar(f"{tabela} {id_origem}: [{categoria}] {detalhe} -> {acao}")

    def por_categoria(self) -> Counter:
        return Counter(e.categoria for e in self.excecoes)

    def confere(self) -> bool:
        """Tudo da origem chegou ao destino? Clientes, processos, solicitantes (N exato) e formulários
        (criados + repetidos que ficaram em outro processo) precisam bater: nada some sem explicação."""
        return all(self.origem[k] == self.destino[k] for k in (
            "clientes", "processos_obt", "processos_ren", "passaportes", "solicitantes", "formularios ds160"))

    def exportar_csv(self, caminho: str | Path):
        """Todas as exceções, num CSV só (`;`, UTF-8 com BOM para abrir no Excel)."""
        with open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
            escritor = csv.writer(arquivo, delimiter=";")
            escritor.writerow(COLUNAS_EXCECOES)
            for e in sorted(self.excecoes, key=lambda e: (e.categoria, e.tabela, e.id_origem)):
                escritor.writerow([e.categoria, e.tabela, e.id_origem, e.cliente_id_origem or "", e.detalhe, e.acao])


# ---------------------------------------------------------------- funções puras (testáveis sem banco)

def chave(nome: str) -> str:
    """Primeiro nome sem acento e em minúsculas: 'José Silva' e 'jose' dão a mesma chave."""
    primeiro = (nome.split() or [""])[0]
    sem_acento = unicodedata.normalize("NFKD", primeiro).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def ler_codigos(texto: str | None) -> tuple[list[tuple[str, str | None]], list[str]]:
    """Lê o campo codigo_ds160 -> ([(codigo, primeiro_nome_ou_None)], notas).

    Tolera as variações reais: traço opcional (`AA00... Maria`), `novo`/`nova DS` com ou sem traço, caixa baixa,
    vários códigos na mesma linha e comentários entre parênteses. `AA00... - novo` é um formulário refeito, da
    mesma pessoa da linha anterior (por isso o nome fica None quando ainda não houve nenhuma pessoa).
    `notas` são as linhas que merecem ir para a observação: sem código nenhum, ou com comentário/texto sobrando."""
    codigos, notas = [], []
    pessoa = None
    for linha in (texto or "").splitlines():
        if not linha.strip():
            continue
        achados = list(CODIGO.finditer(linha))
        if not achados:
            notas.append(linha.strip())
            continue
        guardar_linha = bool(linha[:achados[0].start()].strip())  # texto antes do 1º código também não se perde
        for i, achado in enumerate(achados):
            fim = achados[i + 1].start() if i + 1 < len(achados) else len(linha)
            resto = linha[achado.end():fim]
            if COMENTARIO.search(resto):
                guardar_linha = True
            resto = COMENTARIO.sub(" ", resto).strip(" \t-–—:;,.")
            if resto and not NOVO.match(resto):
                primeira = resto.split()[0]
                if NOME.match(primeira):
                    pessoa = primeira
                else:
                    guardar_linha = True
            codigos.append((achado.group(0).upper(), pessoa))
        if guardar_linha:
            notas.append(linha.strip())
    return codigos, notas


def montar_solicitantes(cliente_nome: str, n: int, codigos: list[tuple[str, str | None]]):
    """Cria os solicitantes do processo e devolve (lista, função que acha o solicitante de um código, excedentes).

    n_solicitantes é a verdade: sempre N pessoas. O titular tem o nome do cliente; os demais começam como
    'Solicitante 2', 3... e ganham, na ordem, o primeiro nome que aparece nos códigos. Nomes além de N não criam
    pessoas: ficam em `excedentes` e os formulários deles vão para o titular."""
    titular = Solicitante(nome=cliente_nome, titular=True)
    extras = [Solicitante(nome=f"Solicitante {i}") for i in range(2, max(n, 1) + 1)]
    todos = [titular, *extras]
    livres = list(extras)
    por_chave: dict[str, Solicitante] = {}
    excedentes: list[str] = []
    for _, pessoa in codigos:
        if pessoa is None:
            continue
        k = chave(pessoa)
        if k in por_chave or any(chave(e) == k for e in excedentes):
            continue
        if k == chave(cliente_nome) and titular not in por_chave.values():
            por_chave[k] = titular
        elif livres:
            extra = livres.pop(0)
            extra.nome = pessoa
            por_chave[k] = extra
        else:
            excedentes.append(pessoa)

    def de_quem(pessoa: str | None) -> Solicitante:
        return por_chave.get(chave(pessoa), titular) if pessoa else titular

    return todos, de_quem, excedentes


def normalizar_email(valor: str | None) -> str | None:
    limpo = (valor or "").strip().lower()
    return limpo or None


def normalizar_telefone(valor: str | None) -> str | None:
    """Mesma regra da API: só dígitos, sem o 55 do Brasil quando sobram mais de 11."""
    digitos = "".join(c for c in (valor or "") if c.isdigit())
    if len(digitos) > 11 and digitos.startswith("55"):
        digitos = digitos[2:]
    return digitos or None


def normalizar_nome(valor: str) -> str:
    """Tira espaços sobrando; nome TODO EM MAIÚSCULAS vira Nome Próprio (da/de/dos ficam minúsculos)."""
    nome = " ".join(valor.split())
    if nome.isupper():
        palavras = nome.lower().split(" ")
        nome = " ".join(p if (i and p in PARTICULAS) else p.capitalize() for i, p in enumerate(palavras))
    return nome


def unificar_grupos(grupos: list[str | None]) -> dict[str, str]:
    """{grupo como veio: grafia única}. Grupos que só diferem em caixa/espaços ficam com a grafia mais comum."""
    contagem: dict[str, Counter] = defaultdict(Counter)
    for g in grupos:
        limpo = " ".join((g or "").split())
        if limpo:
            contagem[limpo.lower()][limpo] += 1
    escolhida = {k: c.most_common(1)[0][0] for k, c in contagem.items()}
    return {g: escolhida[" ".join(g.split()).lower()] for g in grupos if g and g.strip()}


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


def _donos_dos_codigos(obt: list[dict], ren: list[dict]) -> dict[str, tuple[str, int, int]]:
    """{código: (tabela, id, cliente_id) do processo que fica com o formulário}.
    Regra: OBT antes de REN (o cliente sai da renovação para a orientação); empate, o maior id."""
    donos: dict[str, tuple[str, int, int]] = {}
    # as listas vêm ordenadas por id e a OBT é lida por último: a última ocorrência é sempre a que vence
    for tabela, linhas in (("REN", ren), ("OBT", obt)):
        for r in linhas:
            for codigo, _ in ler_codigos(r.get("codigo_ds160"))[0]:
                donos[codigo] = (tabela, r["id"], r["cliente_id"])
    return donos


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

    # ---- clientes (padronizados)
    clientes_origem = origem.todos("clientes")
    grupo_unico = unificar_grupos([c["grupo"] for c in clientes_origem])
    cliente_novo: dict[int, Cliente] = {}
    for c in clientes_origem:
        nome, email = normalizar_nome(c["nome"]), normalizar_email(c["email"])
        telefone, grupo = normalizar_telefone(c["telefone"]), grupo_unico.get(c["grupo"])
        for campo, antes, depois in (("nome", c["nome"], nome), ("email", c["email"], email),
                                     ("telefone", c["telefone"], telefone), ("grupo", c["grupo"], grupo)):
            if (antes or None) != depois:
                relatorio.normalizados[f"cliente.{campo}"] += 1
        cliente = Cliente(nome=nome, email=email, telefone=telefone, grupo=grupo)
        sessao.add(cliente)
        cliente_novo[c["id"]] = cliente
    sessao.flush()
    relatorio.origem["clientes"] = len(cliente_novo)

    obt = origem.todos("processos_obt")
    ren = origem.todos("processos_ren")
    pas = origem.todos("passaportes")
    donos = _donos_dos_codigos(obt, ren)
    esperados = {"solicitantes": 0, "formularios": 0}
    repetidos = {"n": 0}

    def solicitantes_e_formularios(processo, cliente: Cliente, r: dict, tabela: str, codigo_ds160: str | None,
                                   status_ds: str | None, resultado: str | None) -> list[str]:
        """Liga ao processo os solicitantes e formulários; devolve linhas extras para a observação."""
        n = r["n_solicitantes"]
        extras_obs: list[str] = []
        codigos, notas = ler_codigos(codigo_ds160)
        for linha in notas:
            extras_obs.append(linha)
            relatorio.registrar("linha_fora_do_padrao", tabela, r["id"], r["cliente_id"], repr(linha[:80]),
                                "mantida na observação")
        todos, de_quem, excedentes = montar_solicitantes(cliente.nome, n, codigos)
        if excedentes:
            relatorio.registrar("nomes_alem_de_n_solicitantes", tabela, r["id"], r["cliente_id"],
                                f"{len(excedentes)} nome(s) a mais que n_solicitantes={n}",
                                "n respeitado; formulários dessas pessoas ficaram no titular")
        if codigos and any(s.nome.startswith("Solicitante ") for s in todos[1:]):
            relatorio.registrar("solicitante_sem_nome", tabela, r["id"], r["cliente_id"],
                                f"n_solicitantes={n}, mas os códigos não nomeiam todos",
                                "ficaram como 'Solicitante N'")
        for s in todos:
            s.resultado = Resultado(resultado) if resultado else Resultado.PROCESSANDO
            processo.solicitantes.append(s)
        esperados["solicitantes"] += max(n, 1)
        status = StatusDS(status_ds) if status_ds else StatusDS.PENDENTE
        criados, vistos = 0, set()
        for codigo, pessoa in codigos:
            esperados["formularios"] += 1
            dono = donos[codigo]
            if codigo in vistos:
                repetidos["n"] += 1
                relatorio.registrar("codigo_repetido_no_processo", tabela, r["id"], r["cliente_id"], codigo,
                                    "contado uma vez")
                continue
            vistos.add(codigo)
            if (dono[0], dono[1]) != (tabela, r["id"]):
                repetidos["n"] += 1
                extras_obs.append(f"Código {codigo} também consta no processo {dono[0]} (origem {dono[1]}), "
                                  "que ficou com o formulário.")
                mesmo = dono[2] == r["cliente_id"]
                relatorio.registrar(
                    "codigo_repetido_mesmo_cliente" if mesmo else "codigo_repetido_outro_cliente",
                    tabela, r["id"], r["cliente_id"], f"{codigo} também em {dono[0]} {dono[1]}",
                    "formulário mantido no processo mais recente" if mesmo else "formulário mantido no mais recente; REVISAR")
                continue
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
            processo, cliente, r, "OBT", r["codigo_ds160"] if tem_cod else None, r["status_ds"], r["resultado"])
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
    for r in ren:
        cliente = cliente_novo[r["cliente_id"]]
        processo = ProcessoREN(
            cliente_id=cliente.id, situacao=r["situacao"], consulado=Consulado(r["consulado"]),
            data_casv=r["data_casv"], docs=DocsREN(r["docs"]), status_rascunho=Rascunho(r["status_rascunho"]),
            endereco=r["endereco"], codigo_rastreio=r["codigo_rastreio"])
        extras = solicitantes_e_formularios(
            processo, cliente, r, "REN", r["codigo_ds160"] if tem_cod else None, r["status_ds"], None)
        processo.observacao = _observacao(r["notas_ds160"] if tem_notas else None, extras)
        grava(processo, r["situacao"])
    relatorio.origem["processos_ren"] = len(ren)

    # ---- passaportes
    for r in pas:
        cliente = cliente_novo[r["cliente_id"]]
        situacao = r["situacao"] or "Pendente"  # regra do negócio: passaporte sem situação é "Pendente"
        if not r["situacao"]:
            relatorio.normalizados["passaporte.situacao vazia -> Pendente"] += 1
        processo = ProcessoPASS(cliente_id=cliente.id, situacao=situacao, data_pf=r["data_pf"],
                                prazo_pf=r["prazo_pf"])
        solicitantes_e_formularios(processo, cliente, r, "PASS", None, None, None)
        grava(processo, situacao)
    relatorio.origem["passaportes"] = len(pas)

    sessao.flush()

    # ---- conferência: origem x destino
    conta = lambda modelo: sessao.scalar(select(func.count()).select_from(modelo))
    relatorio.destino = {
        "clientes": conta(Cliente), "processos_obt": conta(ProcessoOBT),
        "processos_ren": conta(ProcessoREN), "passaportes": conta(ProcessoPASS)}
    relatorio.origem["solicitantes"] = esperados["solicitantes"]  # soma de n_solicitantes (N exato)
    relatorio.destino["solicitantes"] = conta(Solicitante)
    relatorio.origem["formularios ds160"] = esperados["formularios"]  # linhas de código lidas
    relatorio.destino["formularios ds160"] = conta(FormularioDS160) + repetidos["n"]  # criados + repetidos explicados
    relatorio.origem["usuarios (do CSV)"] = len(usuario_por_funcionario)
    relatorio.destino["usuarios (do CSV)"] = conta(Usuario)
    return relatorio
