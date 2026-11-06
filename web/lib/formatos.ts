import type { TipoProcesso } from "@/lib/tipos";

/** Saudação pela hora do dia (horário de Brasília). */
export function saudacao(agora: Date = new Date()): string {
  const hora = Number(
    new Intl.DateTimeFormat("pt-BR", {
      hour: "numeric",
      hourCycle: "h23",
      timeZone: "America/Sao_Paulo",
    }).format(agora),
  );
  if (hora < 5) return "Boa noite";
  if (hora < 12) return "Bom dia";
  if (hora < 18) return "Boa tarde";
  return "Boa noite";
}

export const TIPOS: Record<TipoProcesso, { nome: string; curto: string }> = {
  OBT: { nome: "Obtenção de visto", curto: "Obtenção" },
  REN: { nome: "Renovação de visto", curto: "Renovação" },
  PASS: { nome: "Passaporte", curto: "Passaporte" },
};

/** Processos que ainda pedem trabalho: tudo que não está concluído. */
export function emAndamento(porSituacao: Record<string, number>): number {
  return Object.entries(porSituacao).reduce(
    (soma, [situacao, n]) => (situacao === "Concluido" ? soma : soma + n),
    0,
  );
}

/** Situações em andamento, da mais cheia para a mais vazia. */
export function situacoesAbertas(porSituacao: Record<string, number>): [string, number][] {
  return Object.entries(porSituacao)
    .filter(([situacao]) => situacao !== "Concluido")
    .sort((a, b) => b[1] - a[1]);
}

/** Nomes como aparecem na tela (o banco guarda sem acento). */
export function rotuloSituacao(situacao: string): string {
  return { Concluido: "Concluído", Credito: "Crédito" }[situacao] ?? situacao;
}
