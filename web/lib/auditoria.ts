/**
 * Auditoria de clientes e processos (só admin): transforma as linhas cruas da API (`antes`/`depois` em JSON,
 * nomes de coluna do banco) em frases para a tela. Funções puras, testáveis.
 */
import { formatarTelefone } from "@/lib/formularios";
import { formatarData } from "@/lib/processos";

export type Alteracao = {
  id: number;
  tabela: string;
  registro_id: number;
  processo_id: number | null;
  cliente_id: number | null;
  acao: "criou" | "editou" | "apagou" | "eliminou";
  antes: Record<string, unknown> | null;
  depois: Record<string, unknown> | null;
  usuario_id: number | null;
  usuario_nome: string | null;
  requisicao: string | null;
  origem: string;
  transacao: number;
  criado_em: string;
};

/** Cliente excluído que ainda tem cópia na auditoria (dá para restaurar ou eliminar de vez). */
export type ClienteExcluido = {
  cliente_id: number;
  nome: string;
  telefone: string | null;
  email: string | null;
  apagado_em: string;
  usuario_id: number | null;
  apagado_por: string | null;
  origem: string;
  n_processos: number;
};

export type Restauracao = {
  cliente_id: number;
  nome: string;
  processos: number;
  pessoas: number;
  formularios: number;
  eventos: number;
  vinculos: number;
};

export type Campo = { rotulo: string; antes: string | null; depois: string | null };
export type Descricao = { id: number; titulo: string; campos: Campo[] };
export type GrupoDeAlteracoes = {
  transacao: number;
  criado_em: string;
  autor: string;
  requisicao: string | null;
  itens: Descricao[];
};

const DETALHES_DO_PROCESSO = new Set(["processo_obt", "processo_ren", "processo_pass"]);

const ROTULOS: Record<string, string> = {
  nome: "Nome",
  email: "E-mail",
  telefone: "Telefone",
  grupo: "Grupo",
  endereco: "Endereço",
  situacao: "Situação",
  observacao: "Observação",
  consulado: "Consulado",
  monitoramento: "Monitoramento",
  data_casv: "Data do CASV",
  data_entrevista: "Data da entrevista",
  data_vencimento_taxa: "Vencimento da taxa",
  data_pf: "Data na PF",
  prazo_pf: "Prazo da PF",
  data_despacho: "Data do despacho",
  despachado_em: "Despachado em",
  status_rascunho: "Rascunho",
  orientacao: "Orientação",
  orientacao_data: "Data da orientação",
  previsao_orientacao: "Orientação prevista",
  orientacao_por_id: "Orientado por",
  codigo_rastreio: "Código de rastreio",
  processo_anterior_id: "Tentativa anterior",
  cliente_id: "Cliente",
  titular: "Titular",
  codigo: "Código",
  status: "Status",
  resultado: "Resultado",
  docs: "Documentos",
  solicitante_id: "Pessoa",
};

/** Colunas técnicas: não dizem nada a quem lê o histórico. */
const OCULTOS = new Set(["id", "processo_id", "tipo", "criado_em", "atualizado_em", "criado_por_id"]);

const ORIGENS: Record<string, string> = {
  seed: "dados de demonstração",
  importacao: "importação do sistema antigo",
  banco: "alteração direta no banco",
};

export function rotuloDoCampo(campo: string): string {
  if (ROTULOS[campo]) return ROTULOS[campo];
  const texto = campo.replaceAll("_", " ");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

export function formatarValor(campo: string, valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  if (typeof valor === "boolean") return valor ? "sim" : "não";
  if (campo === "telefone" && typeof valor === "string") return formatarTelefone(valor);
  if (campo === "orientacao_por_id") return `usuário #${valor}`;
  if (campo.endsWith("_id")) return `#${valor}`;
  if (typeof valor === "string" && /^\d{4}-\d{2}-\d{2}/.test(valor)) return formatarData(valor);
  return String(valor);
}

/** Quem fez: o nome da pessoa; sem usuário, de onde veio a mudança. */
export function autorDaAlteracao(a: Pick<Alteracao, "usuario_id" | "usuario_nome" | "origem">): string {
  if (a.usuario_nome) return a.usuario_nome;
  if (a.usuario_id !== null) return `usuário #${a.usuario_id}`;
  return ORIGENS[a.origem] ?? a.origem;
}

const texto = (registro: Record<string, unknown> | null, campo: string) => String(registro?.[campo] ?? "");

function titulo(a: Alteracao): string | null {
  const r = a.acao === "apagou" ? a.antes : a.depois;
  if (a.tabela === "eventos") return null; // a linha do tempo do processo já mostra; só serve à restauração
  if (a.origem === "restauracao") {
    // uma restauração recoloca dezenas de linhas: no histórico vira uma frase só, no cliente
    if (a.tabela === "clientes" && a.acao === "criou")
      return `Cliente restaurado da exclusão: ${texto(r, "nome")}`;
    return null;
  }
  if (a.tabela === "clientes" && a.acao === "eliminou")
    return `Cliente nº ${a.registro_id} eliminado definitivamente`;
  switch (a.tabela) {
    case "clientes":
      if (a.acao === "criou") return `Cliente cadastrado: ${texto(r, "nome")}`;
      if (a.acao === "apagou") return `Cliente apagado: ${texto(r, "nome")}`;
      return "Dados do cliente editados";
    case "processos":
      if (a.acao === "criou")
        return `Processo ${texto(r, "tipo")} #${a.registro_id} aberto em ${texto(r, "situacao")}`;
      if (a.acao === "apagou") return `Processo ${texto(r, "tipo")} #${a.registro_id} apagado`;
      return a.depois && "situacao" in a.depois ? "Situação alterada" : `Processo #${a.registro_id} editado`;
    case "solicitantes":
      if (a.acao === "criou") return `Pessoa incluída: ${texto(r, "nome")}${r?.titular ? " (titular)" : ""}`;
      if (a.acao === "apagou") return `Pessoa removida: ${texto(r, "nome")}`;
      return `Pessoa #${a.registro_id} editada`;
    case "formularios_ds160":
      if (a.acao === "criou") return `DS-160 ${texto(r, "codigo")} cadastrado`;
      if (a.acao === "apagou") return `DS-160 ${texto(r, "codigo")} removido`;
      return `DS-160 #${a.registro_id} editado`;
    default:
      // detalhes do OBT/REN/PASS: ao criar e apagar, a linha de `processos` já conta a história
      if (DETALHES_DO_PROCESSO.has(a.tabela))
        return a.acao === "editou" ? `Processo #${a.registro_id} editado` : null;
      return `${a.tabela} #${a.registro_id}: ${a.acao}`;
  }
}

/**
 * Uma linha da auditoria em linguagem de gente. `null` = não vale mostrar (ex.: a parte de detalhe de um
 * processo criado, que repetiria a linha do processo).
 * - editou: cada campo que mudou, com antes e depois;
 * - apagou: os dados que existiam (é daqui que se recupera um cadastro apagado por engano);
 * - criou: só o título.
 */
export function descreverAlteracao(a: Alteracao): Descricao | null {
  const t = titulo(a);
  if (t === null) return null;
  let campos: Campo[] = [];
  if (a.acao === "editou") {
    campos = Object.keys(a.depois ?? {})
      .filter((c) => !OCULTOS.has(c))
      .map((c) => ({
        rotulo: rotuloDoCampo(c),
        antes: formatarValor(c, a.antes?.[c]),
        depois: formatarValor(c, a.depois?.[c]),
      }));
    if (campos.length === 0) return null; // só mudou coluna técnica
  } else if (a.acao === "eliminou") {
    campos = [{ rotulo: "Motivo", antes: String(a.depois?.motivo ?? "—"), depois: null }];
  } else if (a.acao === "apagou") {
    campos = Object.entries(a.antes ?? {})
      .filter(([c, v]) => !OCULTOS.has(c) && v !== null && v !== "")
      .map(([c, v]) => ({ rotulo: rotuloDoCampo(c), antes: formatarValor(c, v), depois: null }));
  }
  return { id: a.id, titulo: t, campos };
}

/**
 * Junta as linhas da mesma transação (ex.: um cliente apagado com seus processos e pessoas) num bloco só.
 * Mantém a ordem recebida (a API manda da mais nova para a mais antiga).
 */
export function agruparAlteracoes(lista: Alteracao[]): GrupoDeAlteracoes[] {
  const grupos: GrupoDeAlteracoes[] = [];
  const porTransacao = new Map<number, GrupoDeAlteracoes>();
  for (const a of lista) {
    const descricao = descreverAlteracao(a);
    if (!descricao) continue;
    let grupo = porTransacao.get(a.transacao);
    if (!grupo) {
      grupo = {
        transacao: a.transacao,
        criado_em: a.criado_em,
        autor: autorDaAlteracao(a),
        requisicao: a.requisicao,
        itens: [],
      };
      porTransacao.set(a.transacao, grupo);
      grupos.push(grupo);
    }
    grupo.itens.push(descricao);
  }
  // dentro do bloco, na ordem em que aconteceu (a lista veio da mais nova para a mais antiga)
  for (const g of grupos) g.itens.reverse();
  return grupos;
}
