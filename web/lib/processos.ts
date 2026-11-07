/** Regras de apresentação dos processos. Funções puras (testáveis sem navegador nem API). */
import type { LinhaPainel, TipoProcesso } from "@/lib/tipos";

// ---------------------------------------------------------------- datas

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/**
 * A API manda datas como "2026-12-01". Lidas como texto, nunca com `new Date("2026-12-01")`: essa forma é
 * interpretada em UTC e, no Brasil, viraria 30/11 às 21h.
 */
export function formatarData(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return a && m && d ? `${d}/${m}/${a}` : "—";
}

export function formatarDataCurta(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [, m, d] = iso.slice(0, 10).split("-");
  return `${d} ${MESES[Number(m) - 1] ?? ""}`;
}

/** Data e hora de um evento (vem com fuso), no horário de Brasília: ["05/11/2026", "14:30"]. */
export function dataEHora(iso: string): [string, string] {
  const momento = new Date(iso);
  const fuso = { timeZone: "America/Sao_Paulo" } as const;
  return [
    new Intl.DateTimeFormat("pt-BR", { ...fuso, day: "2-digit", month: "2-digit", year: "numeric" }).format(
      momento,
    ),
    new Intl.DateTimeFormat("pt-BR", {
      ...fuso,
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(momento),
  ];
}

// ---------------------------------------------------------------- situação e resultado

export type Tom = "pagamento" | "andamento" | "parado" | "concluido" | "aprovado" | "negado" | "parcial";

const TOM_DA_SITUACAO: Record<string, Tom> = {
  "Pagamento Pendente": "pagamento",
  Boleto: "pagamento",
  Credito: "pagamento",
  Pix: "pagamento",
  Limbo: "parado",
  Administrativo: "parado",
  Concluido: "concluido",
};

export function tomDaSituacao(situacao: string): Tom {
  return TOM_DA_SITUACAO[situacao] ?? "andamento";
}

export function tomDoResultado(resultado: string): Tom {
  return (
    ({ Aprovado: "aprovado", Negado: "negado", Parcial: "parcial" } as Record<string, Tom>)[resultado] ??
    "andamento"
  );
}

/**
 * O resultado "Processando" (o consulado ainda não respondeu) aparece como "Aguardando", para não se
 * confundir com a situação "Processando" do fluxo. O valor enviado à API continua o mesmo.
 */
export function rotuloResultado(resultado: string): string {
  return resultado === "Processando" ? "Aguardando" : resultado;
}

/** Classes de cor por tom (selos de situação e resultado). */
export const CLASSES_DO_TOM: Record<Tom, string> = {
  pagamento: "bg-alerta-suave text-alerta",
  andamento: "bg-marca-suave text-accent-foreground",
  parado: "bg-muted text-muted-foreground",
  concluido: "bg-sucesso-suave text-sucesso",
  aprovado: "bg-sucesso-suave text-sucesso",
  negado: "bg-perigo-suave text-perigo",
  parcial: "bg-alerta-suave text-alerta",
};

// ---------------------------------------------------------------- orientação (OBT)

/**
 * Status da orientação, na ordem do caminho, cada um com a sua cor (como a equipe fazia na planilha).
 * Os valores são os da API (app/enums.py, Orientacao).
 */
export const ORIENTACOES = [
  { valor: "Pendente", classes: "bg-muted text-muted-foreground", dica: "Opções ainda não enviadas" },
  { valor: "Opções enviadas", classes: "bg-ceu-suave text-ceu", dica: "Recebeu as opções (Opt A ou padrão)" },
  { valor: "Sem resposta", classes: "bg-lilas-suave text-lilas", dica: "Recebeu as opções e não respondeu" },
  {
    valor: "Opt A",
    classes: "bg-tinta text-papel dark:bg-papel dark:text-tinta",
    dica: "Escolheu a Opt A",
  },
  { valor: "Escolheu padrão", classes: "bg-alerta-suave text-alerta", dica: "Falta agendar a orientação" },
  {
    valor: "Agendada",
    classes: "bg-marca-suave text-accent-foreground",
    dica: "Orientação com data marcada",
  },
  { valor: "Fornecidas", classes: "bg-sucesso-suave text-sucesso", dica: "Orientação feita" },
] as const;

export type Orientacao = (typeof ORIENTACOES)[number]["valor"];

export function dadosDaOrientacao(valor: string | null | undefined) {
  return ORIENTACOES.find((o) => o.valor === valor) ?? null;
}

// ---------------------------------------------------------------- datas que importam em cada tipo

export type DataDoProcesso = { rotulo: string; valor: string | null };

export function datasPrincipais(linha: LinhaPainel): DataDoProcesso[] {
  switch (linha.tipo) {
    case "OBT":
      return [
        { rotulo: "CASV", valor: linha.data_casv },
        { rotulo: "Entrevista", valor: linha.data_entrevista },
      ];
    case "REN":
      return [
        { rotulo: "CASV", valor: linha.data_casv },
        { rotulo: "Despacho", valor: linha.data_despacho },
      ];
    case "PASS":
      return [
        { rotulo: "PF", valor: linha.data_pf },
        { rotulo: "Prazo", valor: linha.prazo_pf },
      ];
  }
}

// ---------------------------------------------------------------- filtros na URL

export const POR_PAGINA = 50;
export const DATAS_FILTRAVEIS = {
  casv: "CASV",
  entrevista: "Entrevista",
  orientacao: "Orientação",
  despacho: "Despacho",
  pf: "Polícia Federal",
  prazo_pf: "Prazo PF",
} as const;
export type DataFiltravel = keyof typeof DATAS_FILTRAVEIS;

/** Quais datas fazem sentido em cada tipo (a API aceita todas, mas só estas existem no tipo). */
export const DATAS_DO_TIPO: Record<TipoProcesso, DataFiltravel[]> = {
  OBT: ["casv", "entrevista", "orientacao"],
  REN: ["casv", "despacho"],
  PASS: ["pf", "prazo_pf"],
};

export type Filtros = {
  tipo: TipoProcesso;
  visao: "tabela" | "quadro";
  situacao?: string;
  consulado?: string;
  resultado?: string;
  cliente?: string;
  data?: DataFiltravel;
  de?: string;
  ate?: string;
  /** só REN: falta despachar ou já despachado */
  despacho?: "pendente" | "feito";
  /** só OBT: em que ponto está a orientação */
  orientacao?: Orientacao;
  pagina: number;
};

type Busca = Record<string, string | string[] | undefined>;
const um = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v)?.trim() || undefined;
const DATA_ISO = /^\d{4}-\d{2}-\d{2}$/;

/** Lê os filtros da URL, descartando o que não for válido (URL editada à mão não quebra a tela). */
export function lerFiltros(busca: Busca): Filtros {
  const tipo = (["OBT", "REN", "PASS"] as const).find((t) => t === um(busca.tipo)) ?? "OBT";
  const data = um(busca.data) as DataFiltravel | undefined;
  const dataValida = data && DATAS_DO_TIPO[tipo].includes(data) ? data : undefined;
  const de = um(busca.de);
  const ate = um(busca.ate);
  const pagina = Number(um(busca.pagina));
  const despacho = um(busca.despacho);
  const orientacao = dadosDaOrientacao(um(busca.orientacao))?.valor;
  return {
    tipo,
    visao: um(busca.visao) === "quadro" ? "quadro" : "tabela",
    situacao: um(busca.situacao),
    consulado: tipo === "PASS" ? undefined : um(busca.consulado),
    resultado: um(busca.resultado),
    cliente: um(busca.cliente),
    data: dataValida,
    de: dataValida && de && DATA_ISO.test(de) ? de : undefined,
    ate: dataValida && ate && DATA_ISO.test(ate) ? ate : undefined,
    despacho: tipo === "REN" && (despacho === "pendente" || despacho === "feito") ? despacho : undefined,
    orientacao: tipo === "OBT" ? orientacao : undefined,
    pagina: Number.isInteger(pagina) && pagina > 0 ? pagina : 1,
  };
}

/** Filtros -> parâmetros da rota /painel da API. */
export function paramsDoPainel(f: Filtros, porPagina = POR_PAGINA) {
  return {
    tipo: f.tipo,
    situacao: f.situacao,
    consulado: f.consulado,
    resultado_geral: f.resultado,
    cliente: f.cliente,
    data: f.de || f.ate ? f.data : undefined,
    de: f.de,
    ate: f.ate,
    despacho: f.despacho,
    orientacao: f.orientacao,
    limit: porPagina,
    offset: (f.pagina - 1) * porPagina,
  };
}

/** Filtros -> query string da tela (sem os valores padrão, para a URL ficar curta). */
export function urlDosFiltros(f: Partial<Filtros>): string {
  const q = new URLSearchParams();
  const padrao: Partial<Record<keyof Filtros, unknown>> = { tipo: "OBT", visao: "tabela", pagina: 1 };
  for (const [chave, valor] of Object.entries(f)) {
    if (valor === undefined || valor === "" || padrao[chave as keyof Filtros] === valor) continue;
    q.set(chave, String(valor));
  }
  const s = q.toString();
  return s ? `/processos?${s}` : "/processos";
}

export function haFiltros(f: Filtros): boolean {
  return Boolean(
    f.situacao || f.consulado || f.resultado || f.cliente || f.de || f.ate || f.despacho || f.orientacao,
  );
}

// ---------------------------------------------------------------- passaporte

/**
 * Linha "de máquina" no pé da página de dados, como nos passaportes (MRZ): só letras A-Z, dígitos e "<".
 * Puramente decorativa, montada com o tipo, o número e o nome do cliente.
 */
export function linhaDeMaquina(tipo: TipoProcesso, id: number, cliente: string): [string, string] {
  const limpo = cliente
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toUpperCase()
    .replace(/[^A-Z ]/g, "")
    .trim()
    .split(/\s+/);
  const sobrenome = limpo.length > 1 ? limpo[limpo.length - 1] : (limpo[0] ?? "");
  const nomes = limpo.slice(0, limpo.length > 1 ? -1 : 1).join("<");
  const linha1 = `P<CVB${sobrenome}<<${nomes}`.padEnd(44, "<").slice(0, 44);
  const linha2 = `${tipo}${String(id).padStart(9, "0")}<BRA<CONCEPT<VISTOS`.padEnd(44, "<").slice(0, 44);
  return [linha1, linha2];
}

/** Inclinação de um carimbo: sempre a mesma para o mesmo evento (não "pula" a cada renderização). */
export function inclinacaoDoCarimbo(id: number): number {
  return ((id * 37) % 15) - 7; // entre -7° e +7°
}
