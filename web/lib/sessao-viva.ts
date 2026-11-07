/**
 * Sessão deslizante, do lado do navegador. Regra pura (sem relógio nem DOM) para dar para testar:
 *  - enquanto a pessoa usa (clica, digita), o token é trocado por um novo, no máximo a cada RENOVAR_A_CADA;
 *  - parada, nada é renovado: AVISO antes de vencer aparece o aviso, e vencida vai para o login;
 *  - a API tem um teto por login (JWT_SESSAO_MAXIMA_HORAS). Chegando nele a renovação é recusada e o aviso
 *    explica que é preciso entrar de novo.
 */

export const RENOVAR_A_CADA = 5 * 60_000;
export const AVISO = 2 * 60_000;
export const INTERVALO_DE_CHECAGEM = 10_000;

export type Decisao = "nada" | "renovar" | "avisar" | "sair";

export type EstadoSessao = {
  agora: number;
  /** Quando a sessão vence (cookie cv_expira); null para sessões abertas antes de existir o cookie. */
  expiraEm: number | null;
  ultimaAtividade: number;
  ultimaRenovacao: number;
  /** A API recusou renovar: chegou o teto da sessão. */
  noLimite: boolean;
};

export function decidir({
  agora,
  expiraEm,
  ultimaAtividade,
  ultimaRenovacao,
  noLimite,
}: EstadoSessao): Decisao {
  if (expiraEm !== null && agora >= expiraEm) return "sair";
  const restante = expiraEm === null ? Infinity : expiraEm - agora;
  const usouDesdeARenovacao = ultimaAtividade > ultimaRenovacao;
  if (
    usouDesdeARenovacao &&
    !noLimite &&
    (expiraEm === null || agora - ultimaRenovacao >= RENOVAR_A_CADA || restante <= AVISO)
  )
    return "renovar";
  if (restante <= AVISO) return "avisar";
  return "nada";
}

/** Lê o cv_expira do document.cookie (ou de qualquer texto no mesmo formato). */
export function lerExpiracao(textoDosCookies: string, nome = "cv_expira"): number | null {
  for (const parte of textoDosCookies.split(";")) {
    const [chave, ...resto] = parte.trim().split("=");
    if (chave === nome) {
      const valor = Number(resto.join("="));
      return Number.isFinite(valor) && valor > 0 ? valor : null;
    }
  }
  return null;
}

/** "1:05", "0:09". */
export function contagem(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

/** Login com o aviso de sessão vencida e o caminho para voltar depois de entrar. */
export function urlDoLogin(caminho: string): string {
  const busca = new URLSearchParams({ expirou: "1" });
  if (caminho && caminho !== "/") busca.set("de", caminho);
  return `/login?${busca.toString()}`;
}
