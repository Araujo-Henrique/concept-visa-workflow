import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { COOKIE_SESSAO } from "@/lib/constantes";
import { ErroApi, mensagemDeErro } from "@/lib/erros";

/**
 * Única porta de saída para a API Python. Roda só no servidor do Next: o token sai do cookie httpOnly
 * e vai no cabeçalho Authorization; o navegador nunca o vê.
 */

export function urlDaApi(): string {
  const url = process.env.API_URL;
  if (!url) throw new Error("Defina API_URL no .env.development (veja .env.example)");
  return url.replace(/\/$/, "");
}

type Parametros = Record<string, string | number | boolean | null | undefined>;

export function montarCaminho(caminho: string, params?: Parametros): string {
  const busca = new URLSearchParams();
  for (const [chave, valor] of Object.entries(params ?? {})) {
    if (valor !== undefined && valor !== null && valor !== "") busca.set(chave, String(valor));
  }
  const qs = busca.toString();
  return qs ? `${caminho}?${qs}` : caminho;
}

type Opcoes = { metodo?: "GET" | "POST" | "PATCH" | "DELETE"; corpo?: unknown; params?: Parametros };

async function chamar(caminho: string, { metodo = "GET", corpo, params }: Opcoes = {}): Promise<Response> {
  const token = (await cookies()).get(COOKIE_SESSAO)?.value;
  if (!token) redirect("/login");

  let resposta: Response;
  try {
    resposta = await fetch(urlDaApi() + montarCaminho(caminho, params), {
      method: metodo,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(corpo !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
      cache: "no-store", // dado de trabalho: sempre o atual
    });
  } catch {
    throw new ErroApi(503, mensagemDeErro(503, null));
  }

  if (resposta.status === 401) redirect("/login?expirou=1");
  if (!resposta.ok) {
    const detail = await resposta.json().then(
      (j) => j?.detail,
      () => null,
    );
    throw new ErroApi(resposta.status, mensagemDeErro(resposta.status, detail));
  }
  return resposta;
}

/** GET de um recurso. */
export async function apiGet<T>(caminho: string, params?: Parametros): Promise<T> {
  return (await chamar(caminho, { params })).json() as Promise<T>;
}

/** GET de uma lista paginada: traz também o total (cabeçalho X-Total-Count), quando a rota informa. */
export async function apiLista<T>(
  caminho: string,
  params?: Parametros,
): Promise<{ itens: T[]; total: number | null }> {
  const resposta = await chamar(caminho, { params });
  const total = resposta.headers.get("X-Total-Count");
  return { itens: (await resposta.json()) as T[], total: total === null ? null : Number(total) };
}

/** POST, PATCH ou DELETE. Devolve o corpo (ou null quando a API responde 204). */
export async function apiEnviar<T = unknown>(
  metodo: "POST" | "PATCH" | "DELETE",
  caminho: string,
  corpo?: unknown,
): Promise<T | null> {
  const resposta = await chamar(caminho, { metodo, corpo });
  return resposta.status === 204 ? null : ((await resposta.json()) as T);
}
