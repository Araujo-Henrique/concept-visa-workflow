"use server";

import { refresh } from "next/cache";

import { apiEnviar, apiLista } from "@/lib/api";
import { tentar } from "@/lib/resultado";
import type { Cliente, ClienteLista } from "@/lib/tipos";

/** Cadastra um cliente. Nome repetido (sem diferenciar maiúsculas) a API recusa com 409. */
export async function criarCliente(corpo: Record<string, unknown>) {
  return tentar(async () => (await apiEnviar<Cliente>("POST", "/clientes", corpo))!);
}

export async function editarCliente(clienteId: number, mudancas: Record<string, unknown>) {
  const r = await tentar(
    async () => (await apiEnviar<Cliente>("PATCH", `/clientes/${clienteId}`, mudancas))!,
  );
  if (r.ok) refresh();
  return r;
}

/** Busca para escolher o cliente de um processo novo (nome, e-mail ou telefone). */
export async function buscarClientes(termo: string): Promise<ClienteLista[]> {
  if (termo.trim().length < 2) return [];
  return (await apiLista<ClienteLista>("/clientes", { busca: termo.trim(), limit: 8 })).itens;
}
