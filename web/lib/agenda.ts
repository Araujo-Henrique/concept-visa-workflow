/**
 * Agenda: datas como texto "AAAA-MM-DD" (nunca `new Date("2026-12-01")`, que é UTC e no Brasil vira o dia
 * anterior). As contas de calendário usam Date.UTC só como calculadora de dias. Funções puras.
 */
import type { AgendaItem, EventoAgenda } from "@/lib/tipos";

export const FUSO = "America/Sao_Paulo";

/** Rótulo e cor de cada compromisso (a cor sempre vem acompanhada do nome: não é a única pista). */
export const EVENTOS: Record<EventoAgenda, { rotulo: string; curto: string; ponto: string; chip: string }> = {
  orientacao: {
    rotulo: "Orientação",
    curto: "ORIENT",
    ponto: "bg-alerta",
    chip: "bg-alerta-suave text-alerta",
  },
  casv: { rotulo: "CASV", curto: "CASV", ponto: "bg-marca", chip: "bg-marca-suave text-accent-foreground" },
  entrevista: {
    rotulo: "Entrevista",
    curto: "ENTREV",
    ponto: "bg-tinta dark:bg-papel",
    chip: "bg-secondary text-secondary-foreground",
  },
  // neutro de propósito: o verde fica para "despachado" e o vermelho para "atrasado"
  despacho: {
    rotulo: "Despacho",
    curto: "DESP",
    ponto: "bg-muted-foreground",
    chip: "bg-muted text-foreground",
  },
  pf: {
    rotulo: "Polícia Federal",
    curto: "PF",
    ponto: "bg-marca-forte",
    chip: "bg-accent text-accent-foreground",
  },
  prazo_pf: { rotulo: "Prazo PF", curto: "PRAZO", ponto: "bg-perigo", chip: "bg-perigo-suave text-perigo" },
};
export const ORDEM_DOS_EVENTOS = Object.keys(EVENTOS) as EventoAgenda[];

const MESES = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];
const SEMANA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
export const CABECALHO_DA_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"];

const MES_ISO = /^(\d{4})-(0[1-9]|1[0-2])$/;

// ---------------------------------------------------------------- dias

/** Hoje no horário de Brasília, como "AAAA-MM-DD". */
export function hojeEmSP(agora: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: FUSO }).format(agora);
}

function emDias(iso: string): number {
  const [a, m, d] = iso.split("-").map(Number);
  return Date.UTC(a!, m! - 1, d!) / 86_400_000;
}

function deDias(n: number): string {
  return new Date(n * 86_400_000).toISOString().slice(0, 10);
}

export function somarDias(iso: string, n: number): string {
  return deDias(emDias(iso) + n);
}

/** Dias corridos de `de` até `ate` (negativo se `ate` vem antes). */
export function diasEntre(de: string, ate: string): number {
  return emDias(ate) - emDias(de);
}

/** 0 = domingo ... 6 = sábado. */
function diaDaSemana(iso: string): number {
  return new Date(emDias(iso) * 86_400_000).getUTCDay();
}

// ---------------------------------------------------------------- mês

/** Mês da URL ("2026-11"); inválido ou ausente vira o mês de hoje. */
export function lerMes(valor: string | string[] | undefined, hoje: string): string {
  const v = Array.isArray(valor) ? valor[0] : valor;
  return v && MES_ISO.test(v) ? v : hoje.slice(0, 7);
}

export function mesVizinho(mes: string, delta: number): string {
  const [a, m] = mes.split("-").map(Number);
  const total = a! * 12 + (m! - 1) + delta;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
}

export function nomeDoMes(mes: string): string {
  const [a, m] = mes.split("-").map(Number);
  return `${MESES[m! - 1]} de ${a}`;
}

/**
 * Dias da grade do mês, de segunda a domingo, completando as semanas com os dias dos meses vizinhos.
 * Sempre semanas inteiras (35 ou 42 dias): cabe com folga no limite de 92 dias da API.
 */
export function gradeDoMes(mes: string): string[] {
  const primeiro = `${mes}-01`;
  const recuo = (diaDaSemana(primeiro) + 6) % 7; // segunda = 0
  const ultimo = somarDias(`${mesVizinho(mes, 1)}-01`, -1);
  const inicio = somarDias(primeiro, -recuo);
  const semanas = Math.ceil((diasEntre(inicio, ultimo) + 1) / 7);
  return Array.from({ length: semanas * 7 }, (_, i) => somarDias(inicio, i));
}

// ---------------------------------------------------------------- compromissos

export function agruparPorDia(itens: AgendaItem[]): Map<string, AgendaItem[]> {
  const dias = new Map<string, AgendaItem[]>();
  for (const item of itens) {
    const dia = item.data.slice(0, 10);
    const lista = dias.get(dia);
    if (lista) lista.push(item);
    else dias.set(dia, [item]);
  }
  return dias;
}

export function contarPorEvento(itens: AgendaItem[]): Partial<Record<EventoAgenda, number>> {
  const contagem: Partial<Record<EventoAgenda, number>> = {};
  for (const { evento } of itens) contagem[evento] = (contagem[evento] ?? 0) + 1;
  return contagem;
}

/** "Hoje", "Amanhã", "Ontem" ou "qua, 12 nov". */
export function rotuloDoDia(dia: string, hoje: string): string {
  const distancia = diasEntre(hoje, dia);
  if (distancia === 0) return "Hoje";
  if (distancia === 1) return "Amanhã";
  if (distancia === -1) return "Ontem";
  const [, m, d] = dia.split("-").map(Number);
  return `${SEMANA[diaDaSemana(dia)]}, ${d} ${MESES[m! - 1]!.slice(0, 3)}`;
}

/** Título longo do dia no painel: "quarta-feira, 12 de novembro". */
export function tituloDoDia(dia: string): string {
  const [, m, d] = dia.split("-").map(Number);
  const nomes = [
    "domingo",
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
  ];
  return `${nomes[diaDaSemana(dia)]}, ${d} de ${MESES[m! - 1]}`;
}

/** Link da agenda (sem o mês atual na URL, para ficar curta). */
export function urlDaAgenda(mes: string, hoje: string): string {
  return mes === hoje.slice(0, 7) ? "/agenda" : `/agenda?mes=${mes}`;
}

// ---------------------------------------------------------------- despacho (REN)

export type EstadoDespacho = "feito" | "atrasado" | "pendente";

/**
 * O prazo do despacho é CASV - 7 (calculado pelo banco). Despachado = feito; sem despacho e com o prazo
 * já passado = atrasado (no próprio dia do prazo ainda está em dia). Sem prazo nem despacho: nada a dizer.
 */
export function estadoDoDespacho(
  prazo: string | null | undefined,
  despachadoEm: string | null | undefined,
  hoje: string,
): EstadoDespacho | null {
  if (despachadoEm) return "feito";
  if (!prazo) return null;
  return prazo.slice(0, 10) < hoje ? "atrasado" : "pendente";
}

export const ESTADOS_DO_DESPACHO: Record<EstadoDespacho, { rotulo: string; classes: string }> = {
  feito: { rotulo: "Despachado", classes: "bg-sucesso-suave text-sucesso" },
  atrasado: { rotulo: "Atrasado", classes: "bg-perigo-suave text-perigo" },
  pendente: { rotulo: "A despachar", classes: "bg-alerta-suave text-alerta" },
};

/** Estado dos despachos de um dia (o pior deles): algum atrasado > algum a despachar > todos feitos. */
export function estadoDosDespachos(itens: AgendaItem[], hoje: string): EstadoDespacho | null {
  const estados = itens
    .filter((i) => i.evento === "despacho")
    .map((i) => estadoDoDespacho(i.data, i.despachado_em, hoje));
  if (estados.includes("atrasado")) return "atrasado";
  if (estados.includes("pendente")) return "pendente";
  return estados.length ? "feito" : null;
}
