"use server";

import { refresh } from "next/cache";

import { apiEnviar, apiGet } from "@/lib/api";
import { tentar } from "@/lib/resultado";
import type { Usuario } from "@/lib/tipos";
import type { RegistroAuditoria } from "@/lib/usuarios";

// Administração de usuários: a API só aceita de quem tem o perfil admin (403 para os demais).

export async function criarUsuario(corpo: { nome: string; email: string; perfil: string; senha: string }) {
  const r = await tentar(async () => (await apiEnviar<Usuario>("POST", "/usuarios", corpo))!);
  if (r.ok) refresh();
  return r;
}

/** Nome, perfil ou ativo. Tirar o último administrador ativo a API recusa (409). */
export async function editarUsuario(
  usuarioId: number,
  mudancas: Partial<Pick<Usuario, "nome" | "perfil" | "ativo">>,
) {
  const r = await tentar(
    async () => (await apiEnviar<Usuario>("PATCH", `/usuarios/${usuarioId}`, mudancas))!,
  );
  if (r.ok) refresh();
  return r;
}

export async function redefinirSenha(usuarioId: number, senha: string) {
  return tentar(() => apiEnviar("POST", `/usuarios/${usuarioId}/senha`, { senha }));
}

export async function auditoriaDoUsuario(usuarioId: number) {
  return tentar(() => apiGet<RegistroAuditoria[]>(`/usuarios/${usuarioId}/auditoria`));
}

/** Qualquer perfil troca a própria senha (precisa da atual). */
export async function trocarMinhaSenha(senhaAtual: string, novaSenha: string) {
  return tentar(() => apiEnviar("POST", "/auth/senha", { senha_atual: senhaAtual, nova_senha: novaSenha }));
}
