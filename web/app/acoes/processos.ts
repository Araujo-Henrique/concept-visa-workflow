"use server";

import { refresh } from "next/cache";

import { apiEnviar, apiLista } from "@/lib/api";
import { ErroApi } from "@/lib/erros";
import type { Evento, LinhaPainel } from "@/lib/tipos";

/**
 * Mutações chamadas pelas telas. Cada uma é tratada como uma rota pública: quem decide se pode é a API
 * (perfil lido do banco a cada chamada). Erros de regra voltam como texto para a tela mostrar.
 */
export type Resultado<T = null> = { ok: true; dados: T } | { ok: false; erro: string };

async function tentar<T>(acao: () => Promise<T>): Promise<Resultado<T>> {
  try {
    return { ok: true, dados: await acao() };
  } catch (erro) {
    if (erro instanceof ErroApi) return { ok: false, erro: erro.message };
    throw erro; // redirect (sessão expirada) e erros inesperados seguem o fluxo normal do Next
  }
}

/** Muda a situação (gera o "carimbo" no histórico). Motivo é obrigatório ao sair de Concluído. */
export async function mudarSituacao(processoId: number, situacao: string, motivo?: string) {
  const r = await tentar(() =>
    apiEnviar<Evento>("POST", `/processos/${processoId}/situacao`, {
      situacao,
      ...(motivo?.trim() ? { motivo: motivo.trim() } : {}),
    }),
  );
  if (r.ok) refresh(); // a tela atual relê os dados (situação, histórico, contagens)
  return r;
}

export async function mudarResultado(solicitanteId: number, resultado: string) {
  const r = await tentar(() => apiEnviar("PATCH", `/solicitantes/${solicitanteId}`, { resultado }));
  if (r.ok) refresh();
  return r;
}

export type ItemBusca = Pick<LinhaPainel, "processo_id" | "tipo" | "cliente" | "situacao" | "n_solicitantes">;

/** Busca global (Ctrl+K): número do processo ou trecho do nome do cliente. */
export async function buscar(termo: string): Promise<ItemBusca[]> {
  const q = termo.trim().replace(/^#/, "");
  if (q.length < 2 && !/^\d+$/.test(q)) return [];
  const params = /^\d+$/.test(q) ? { processo_id: Number(q), limit: 1 } : { cliente: q, limit: 8 };
  const { itens } = await apiLista<LinhaPainel>("/painel", params);
  return itens.map(({ processo_id, tipo, cliente, situacao, n_solicitantes }) => ({
    processo_id,
    tipo,
    cliente,
    situacao,
    n_solicitantes,
  }));
}
