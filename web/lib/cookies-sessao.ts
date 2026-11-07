import "server-only";

import { cookies } from "next/headers";

import { COOKIE_EXPIRA, COOKIE_SESSAO } from "@/lib/constantes";

/**
 * Grava a sessão: o token num cookie httpOnly (o navegador nunca o lê) e, ao lado, quando ele vence
 * (esse o navegador lê, para renovar enquanto a pessoa usa o sistema). Os dois com a validade do token.
 */
export async function gravarSessao(token: string, minutos: number, agora = Date.now()) {
  const jarra = await cookies();
  const comum = {
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: minutos * 60,
  };
  jarra.set(COOKIE_SESSAO, token, { ...comum, httpOnly: true });
  jarra.set(COOKIE_EXPIRA, String(agora + minutos * 60_000), { ...comum, httpOnly: false });
}

export async function apagarSessao() {
  const jarra = await cookies();
  jarra.delete(COOKIE_SESSAO);
  jarra.delete(COOKIE_EXPIRA);
}
