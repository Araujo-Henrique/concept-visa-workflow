"use server";

import { refresh } from "next/cache";

import { apiEnviar, apiLista } from "@/lib/api";
import { tentar } from "@/lib/resultado";
import type {
  Evento,
  Formulario,
  LinhaPainel,
  ProcessoDetalhe,
  Solicitante,
  TipoProcesso,
} from "@/lib/tipos";

/**
 * Mutações chamadas pelas telas. Cada uma é tratada como uma rota pública: quem decide se pode é a API
 * (perfil lido do banco a cada chamada). Erros de regra voltam como texto para a tela mostrar.
 */

const ROTA: Record<TipoProcesso, string> = {
  OBT: "/processos-obt",
  REN: "/processos-ren",
  PASS: "/processos-pass",
};

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

/** Cria o processo (o titular, os extras e o evento "criado" nascem juntos, numa transação da API). */
export async function criarProcesso(tipo: TipoProcesso, corpo: Record<string, unknown>) {
  return tentar(async () => (await apiEnviar<ProcessoDetalhe>("POST", ROTA[tipo], corpo))!);
}

/** Edita os dados (só o que mudou). A situação não muda por aqui: muda pela rota do processo. */
export async function editarProcesso(
  tipo: TipoProcesso,
  processoId: number,
  mudancas: Record<string, unknown>,
) {
  const r = await tentar(() => apiEnviar("PATCH", `${ROTA[tipo]}/${processoId}`, mudancas));
  if (r.ok) refresh();
  return r;
}

// ---------------------------------------------------------------- pessoas e DS-160

async function eAtualizar<T>(acao: () => Promise<T>) {
  const r = await tentar(acao);
  if (r.ok) refresh();
  return r;
}

export async function mudarResultado(solicitanteId: number, resultado: string) {
  return eAtualizar(() => apiEnviar("PATCH", `/solicitantes/${solicitanteId}`, { resultado }));
}

export async function adicionarSolicitante(processoId: number, nome: string) {
  return eAtualizar(() => apiEnviar<Solicitante>("POST", `/processos/${processoId}/solicitantes`, { nome }));
}

export async function tornarTitular(solicitanteId: number) {
  return eAtualizar(() => apiEnviar("POST", `/solicitantes/${solicitanteId}/titular`));
}

export async function removerSolicitante(solicitanteId: number) {
  return eAtualizar(() => apiEnviar("DELETE", `/solicitantes/${solicitanteId}`));
}

export async function adicionarFormulario(solicitanteId: number, codigo: string, status: string) {
  return eAtualizar(() =>
    apiEnviar<Formulario>("POST", `/solicitantes/${solicitanteId}/formularios-ds160`, { codigo, status }),
  );
}

export async function mudarStatusFormulario(formularioId: number, status: string) {
  return eAtualizar(() => apiEnviar("PATCH", `/formularios-ds160/${formularioId}`, { status }));
}

export async function removerFormulario(formularioId: number) {
  return eAtualizar(() => apiEnviar("DELETE", `/formularios-ds160/${formularioId}`));
}

// ---------------------------------------------------------------- busca global

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
