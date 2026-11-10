/**
 * Login com o Google, lado do front: funções puras (testáveis). Quem fala com o Google de verdade e confere o
 * id_token é a API; aqui só se monta o endereço de ida e se guarda o que precisa voltar.
 *
 * Proteções do fluxo (OpenID Connect, código de autorização):
 *  - state: um valor aleatório que sai e volta; sem ele, qualquer site poderia "entregar" um login alheio;
 *  - PKCE (code_verifier/challenge): o código só serve para quem o pediu;
 *  - nonce: amarra o id_token a ESTE login (a API confere).
 * Os três ficam num cookie httpOnly de 10 minutos, só do caminho do login.
 */

export const COOKIE_OAUTH = "cv_oauth";
export const CAMINHO_DA_VOLTA = "/api/auth/google/callback";
export const MINUTOS_DO_LOGIN = 10;
/** O cookie do login em andamento só viaja nas rotas do próprio login. */
export const CAMINHO_DO_COOKIE = "/api/auth/google";

export type EstadoOAuth = { state: string; nonce: string; verificador: string; destino: string };

function base64url(bytes: Uint8Array): string {
  let texto = "";
  for (const b of bytes) texto += String.fromCharCode(b);
  return btoa(texto).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Texto aleatório e imprevisível (gerador criptográfico), seguro para URL. 32 bytes dão 43 caracteres. */
export function aleatorio(bytes = 32): string {
  return base64url(crypto.getRandomValues(new Uint8Array(bytes)));
}

/** PKCE método S256: base64url(sha256(verificador)). */
export async function desafioPkce(verificador: string): Promise<string> {
  const resumo = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verificador));
  return base64url(new Uint8Array(resumo));
}

type Cabecalhos = { get(nome: string): string | null };

/**
 * Endereço do site como a pessoa o vê (ex.: https://algo.ngrok-free.dev ou http://localhost:3000): é nele que
 * o Google devolve o login, e precisa ser idêntico ao cadastrado no Google Cloud. `APP_URL`, se definido,
 * manda; senão vale o que o ngrok/nginx informam (X-Forwarded-*), com o Host como último recurso.
 */
export function origemDoSite(cabecalhos: Cabecalhos, appUrl?: string | null): string {
  if (appUrl?.trim()) return new URL(appUrl.trim()).origin;
  const primeiro = (nome: string) => cabecalhos.get(nome)?.split(",")[0]?.trim() || null;
  const host = primeiro("x-forwarded-host") ?? primeiro("host");
  if (!host || !/^[a-z0-9.-]+(:\d{1,5})?$/i.test(host)) throw new Error("Endereço do site desconhecido");
  const proto = primeiro("x-forwarded-proto");
  return `${proto === "https" ? "https" : "http"}://${host}`;
}

export function urlDeVolta(origem: string): string {
  return origem + CAMINHO_DA_VOLTA;
}

export function urlDoGoogle(p: {
  clientId: string;
  redirectUri: string;
  state: string;
  nonce: string;
  desafio: string;
}): string {
  const busca = new URLSearchParams({
    client_id: p.clientId,
    redirect_uri: p.redirectUri,
    response_type: "code",
    scope: "openid email profile",
    state: p.state,
    nonce: p.nonce,
    code_challenge: p.desafio,
    code_challenge_method: "S256",
    prompt: "select_account", // deixa escolher a conta (quem tem várias não entra sem querer na errada)
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${busca}`;
}

/** Lê o cookie do login em andamento; qualquer coisa fora do formato vira null. */
export function lerEstado(bruto: string | undefined): EstadoOAuth | null {
  if (!bruto) return null;
  try {
    const e = JSON.parse(bruto) as Partial<EstadoOAuth>;
    const ok = [e.state, e.nonce, e.verificador, e.destino].every((v) => typeof v === "string" && v);
    return ok ? (e as EstadoOAuth) : null;
  } catch {
    return null;
  }
}

/** Mensagens da tela de login para cada motivo de volta do Google (`/login?erro=...`). */
export const ERROS_DO_GOOGLE: Record<string, string> = {
  google_sem_acesso:
    "Este e-mail não tem acesso ao sistema. Peça a um administrador para cadastrá-lo e tente de novo.",
  google_cancelado: "O login com o Google foi cancelado.",
  google_expirou: "O login demorou demais ou foi aberto em outra janela. Tente de novo.",
  google_muitas: "Muitas tentativas seguidas. Aguarde um pouco e tente de novo.",
  google_indisponivel: "O login com o Google não está disponível agora. Fale com um administrador.",
  google_falhou: "Não foi possível entrar com o Google. Tente de novo.",
  google_api_fora: "Não consegui falar com o servidor. A API está ligada?",
};

export function mensagemDoErroGoogle(codigo: string | null | undefined): string | undefined {
  return codigo && Object.hasOwn(ERROS_DO_GOOGLE, codigo) ? ERROS_DO_GOOGLE[codigo] : undefined;
}
