import { headers } from "next/headers";
import { NextResponse } from "next/server";

import { urlDaApi } from "@/lib/api";
import { destinoSeguro } from "@/lib/erros";
import {
  aleatorio,
  CAMINHO_DO_COOKIE,
  COOKIE_OAUTH,
  desafioPkce,
  MINUTOS_DO_LOGIN,
  origemDoSite,
  urlDeVolta,
  urlDoGoogle,
  type EstadoOAuth,
} from "@/lib/google-oauth";
import { cabecalhoDoCliente } from "@/lib/ip-cliente";

/**
 * Primeiro passo do "Entrar com o Google": guarda state, nonce e o verificador PKCE num cookie httpOnly e
 * manda a pessoa para o Google. Rota pública (o proxy deixa passar `api/`): quem ainda não entrou chega aqui.
 */
export async function GET(request: Request) {
  const origem = origemDoSite(await headers(), process.env.APP_URL);
  const aoLogin = (erro: string) => NextResponse.redirect(`${origem}/login?erro=${erro}`);

  let clientId: string;
  try {
    const r = await fetch(`${urlDaApi()}/auth/google/config`, {
      headers: await cabecalhoDoCliente(),
      cache: "no-store",
    });
    if (!r.ok) return aoLogin("google_indisponivel");
    clientId = ((await r.json()) as { client_id: string }).client_id;
  } catch {
    return aoLogin("google_api_fora");
  }

  const estado: EstadoOAuth = {
    state: aleatorio(),
    nonce: aleatorio(),
    verificador: aleatorio(),
    destino: destinoSeguro(new URL(request.url).searchParams.get("de")),
  };
  const resposta = NextResponse.redirect(
    urlDoGoogle({
      clientId,
      redirectUri: urlDeVolta(origem),
      state: estado.state,
      nonce: estado.nonce,
      desafio: await desafioPkce(estado.verificador),
    }),
  );
  resposta.cookies.set(COOKIE_OAUTH, JSON.stringify(estado), {
    httpOnly: true,
    secure: origem.startsWith("https://"),
    sameSite: "lax", // precisa voltar junto na navegação que vem do Google
    path: CAMINHO_DO_COOKIE,
    maxAge: MINUTOS_DO_LOGIN * 60,
  });
  return resposta;
}
