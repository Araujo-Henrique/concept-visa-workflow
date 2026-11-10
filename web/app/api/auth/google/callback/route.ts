import { cookies, headers } from "next/headers";
import { NextResponse } from "next/server";

import { urlDaApi } from "@/lib/api";
import { gravarSessao } from "@/lib/cookies-sessao";
import { CAMINHO_DO_COOKIE, COOKIE_OAUTH, lerEstado, origemDoSite, urlDeVolta } from "@/lib/google-oauth";
import { cabecalhoDoCliente } from "@/lib/ip-cliente";

/**
 * Volta do Google. Confere o `state`, entrega o código (e o verificador PKCE) à API, que o troca e confere o
 * id_token, e só entra quem tem o e-mail cadastrado e ativo. Qualquer problema volta ao login com um motivo
 * (`?erro=`) que a tela traduz; nada do Google aparece na URL.
 */
export async function GET(request: Request) {
  const origem = origemDoSite(await headers(), process.env.APP_URL);
  const terminar = (caminho: string) => {
    const resposta = NextResponse.redirect(origem + caminho);
    // o cookie do login em andamento é de uso único
    // data no passado (e não só maxAge: 0): o Next reescreve os cookies da resposta ao gravar a sessão e
    // perdia o Max-Age=0, deixando o cookie vazio no navegador em vez de apagá-lo
    resposta.cookies.set(COOKIE_OAUTH, "", { path: CAMINHO_DO_COOKIE, expires: new Date(0), maxAge: 0 });
    return resposta;
  };
  const falha = (erro: string) => terminar(`/login?erro=${erro}`);

  const estado = lerEstado((await cookies()).get(COOKIE_OAUTH)?.value);
  if (!estado) return falha("google_expirou");

  const busca = new URL(request.url).searchParams;
  const erroDoGoogle = busca.get("error");
  if (erroDoGoogle) return falha(erroDoGoogle === "access_denied" ? "google_cancelado" : "google_falhou");
  const code = busca.get("code");
  if (!code || busca.get("state") !== estado.state) return falha("google_falhou");

  let resposta: Response;
  try {
    resposta = await fetch(`${urlDaApi()}/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(await cabecalhoDoCliente()) },
      body: JSON.stringify({
        code,
        code_verifier: estado.verificador,
        nonce: estado.nonce,
        redirect_uri: urlDeVolta(origem),
      }),
      cache: "no-store",
    });
  } catch {
    return falha("google_api_fora");
  }
  if (resposta.status === 403) return falha("google_sem_acesso");
  if (resposta.status === 429) return falha("google_muitas");
  if (!resposta.ok) return falha("google_falhou");

  const { access_token, expira_em_minutos } = (await resposta.json()) as {
    access_token: string;
    expira_em_minutos: number;
  };
  await gravarSessao(access_token, expira_em_minutos);
  return terminar(estado.destino);
}
