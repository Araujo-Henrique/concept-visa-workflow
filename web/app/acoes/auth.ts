"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import * as z from "zod";

import { urlDaApi } from "@/lib/api";
import { COOKIE_SESSAO } from "@/lib/constantes";
import { mensagemDeErro } from "@/lib/erros";

export type EstadoLogin = { erro?: string; ok?: boolean; primeiroNome?: string } | undefined;

const Credenciais = z.object({
  email: z.email({ error: "Informe um e-mail válido." }).trim(),
  senha: z.string().min(1, { error: "Informe a senha." }),
});

/** Troca e-mail e senha pelo token da API e o guarda num cookie httpOnly com a mesma validade do token. */
export async function entrar(_anterior: EstadoLogin, form: FormData): Promise<EstadoLogin> {
  const dados = Credenciais.safeParse({ email: form.get("email"), senha: form.get("senha") });
  if (!dados.success) return { erro: dados.error.issues[0]?.message };

  let resposta: Response;
  try {
    resposta = await fetch(`${urlDaApi()}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados.data),
      cache: "no-store",
    });
  } catch {
    return { erro: "Não consegui falar com o servidor. A API está ligada?" };
  }
  if (resposta.status === 401) return { erro: "E-mail ou senha incorretos." };
  if (!resposta.ok) {
    const detail = await resposta.json().then(
      (j) => j?.detail,
      () => null,
    );
    return { erro: mensagemDeErro(resposta.status, detail) };
  }

  const { access_token, expira_em_minutos } = (await resposta.json()) as {
    access_token: string;
    expira_em_minutos: number;
  };
  (await cookies()).set(COOKIE_SESSAO, access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: expira_em_minutos * 60,
  });

  // nome para o carimbo de boas-vindas (o perfil é sempre lido de novo pela API em cada tela)
  const eu = await fetch(`${urlDaApi()}/auth/eu`, {
    headers: { Authorization: `Bearer ${access_token}` },
    cache: "no-store",
  }).then(
    (r) => (r.ok ? r.json() : null),
    () => null,
  );
  return { ok: true, primeiroNome: eu?.nome?.split(" ")[0] };
}

export async function sair() {
  (await cookies()).delete(COOKIE_SESSAO);
  redirect("/login");
}
