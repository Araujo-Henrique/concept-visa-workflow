"use server";

import { refresh } from "next/cache";

import { apiEnviar } from "@/lib/api";
import type { Restauracao } from "@/lib/auditoria";
import { tentar } from "@/lib/resultado";

// Clientes excluídos (só admin: a API devolve 403 aos demais). Restaurar traz o cliente de volta com tudo;
// eliminar apaga também a cópia guardada na auditoria e não tem volta.

/** Traz o cliente excluído de volta, com processos, pessoas, DS-160 e histórico, com os mesmos números. */
export async function restaurarCliente(clienteId: number) {
  const r = await tentar(
    async () => (await apiEnviar<Restauracao>("POST", `/auditoria/apagados/${clienteId}/restaurar`))!,
  );
  if (r.ok) refresh();
  return r;
}

/** ELIMINAÇÃO DEFINITIVA. A API confere o nome e exige o motivo (não escreva dado pessoal nele). */
export async function eliminarCliente(clienteId: number, nomeConfirmado: string, motivo: string) {
  const r = await tentar(async () =>
    apiEnviar("POST", `/auditoria/apagados/${clienteId}/eliminar`, {
      nome_confirmado: nomeConfirmado,
      motivo: motivo.trim(),
    }),
  );
  if (r.ok) refresh();
  return r;
}
