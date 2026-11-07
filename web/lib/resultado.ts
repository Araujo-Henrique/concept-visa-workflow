import "server-only";

import { ErroApi } from "@/lib/erros";

/** Resposta das ações para a tela: deu certo (com os dados) ou a mensagem de erro já em português. */
export type Resultado<T = null> = { ok: true; dados: T } | { ok: false; erro: string };

export async function tentar<T>(acao: () => Promise<T>): Promise<Resultado<T>> {
  try {
    return { ok: true, dados: await acao() };
  } catch (erro) {
    if (erro instanceof ErroApi) return { ok: false, erro: erro.message };
    throw erro; // redirect (sessão expirada) e erros inesperados seguem o fluxo normal do Next
  }
}
