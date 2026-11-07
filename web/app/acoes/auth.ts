"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import * as z from "zod";

import { urlDaApi } from "@/lib/api";
import { COOKIE_SESSAO } from "@/lib/constantes";
import { apagarSessao, gravarSessao } from "@/lib/cookies-sessao";
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

  // configuração ausente é um problema diferente de "API desligada": diz o que falta em vez de confundir
  let base: string;
  try {
    base = urlDaApi();
  } catch {
    return { erro: "Configuração incompleta: defina API_URL em web/.env.development (veja .env.example)." };
  }

  let resposta: Response;
  try {
    resposta = await fetch(`${base}/auth/login`, {
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
  await gravarSessao(access_token, expira_em_minutos);

  // nome para o carimbo de boas-vindas (o perfil é sempre lido de novo pela API em cada tela)
  const eu = await fetch(`${base}/auth/eu`, {
    headers: { Authorization: `Bearer ${access_token}` },
    cache: "no-store",
  }).then(
    (r) => (r.ok ? r.json() : null),
    () => null,
  );
  return { ok: true, primeiroNome: eu?.nome?.split(" ")[0] };
}

export async function sair() {
  await apagarSessao();
  redirect("/login");
}

export type Renovacao =
  { ok: true; expiraEm: number } | { ok: false; motivo: "limite" | "expirou" | "falha" };

/**
 * Sessão deslizante: troca o token atual (ainda válido) por um novo na API e regrava os cookies. Chamada
 * pelo navegador enquanto a pessoa usa o sistema. Não redireciona: quem chamou decide o que mostrar.
 */
export async function renovarSessao(): Promise<Renovacao> {
  const token = (await cookies()).get(COOKIE_SESSAO)?.value;
  if (!token) return { ok: false, motivo: "expirou" };
  let resposta: Response;
  try {
    resposta = await fetch(`${urlDaApi()}/auth/renovar`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch {
    return { ok: false, motivo: "falha" };
  }
  if (resposta.status === 401) {
    const detail = await resposta.json().then(
      (j) => String(j?.detail ?? ""),
      () => "",
    );
    return { ok: false, motivo: /limite/i.test(detail) ? "limite" : "expirou" };
  }
  if (resposta.status === 403) return { ok: false, motivo: "expirou" }; // acesso desativado
  if (!resposta.ok) return { ok: false, motivo: "falha" };
  const { access_token, expira_em_minutos } = (await resposta.json()) as {
    access_token: string;
    expira_em_minutos: number;
  };
  const agora = Date.now();
  await gravarSessao(access_token, expira_em_minutos, agora);
  return { ok: true, expiraEm: agora + expira_em_minutos * 60_000 };
}
