/** @jest-environment node */
import {
  aleatorio,
  desafioPkce,
  ERROS_DO_GOOGLE,
  lerEstado,
  mensagemDoErroGoogle,
  origemDoSite,
  urlDeVolta,
  urlDoGoogle,
} from "@/lib/google-oauth";

const cab = (dados: Record<string, string>) => new Headers(dados);

describe("valores aleatórios do login", () => {
  it("32 bytes dão 43 caracteres seguros para URL (o mínimo do PKCE) e nunca se repetem", () => {
    const a = aleatorio();
    expect(a).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(new Set(Array.from({ length: 50 }, () => aleatorio())).size).toBe(50);
  });

  it("o desafio PKCE segue o exemplo oficial da RFC 7636 (S256)", async () => {
    expect(await desafioPkce("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")).toBe(
      "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
    );
  });
});

describe("origemDoSite (o endereço que o Google deve devolver)", () => {
  it("atrás do ngrok/nginx vale o que eles informam", () => {
    const h = cab({
      "x-forwarded-host": "algo.ngrok-free.dev",
      "x-forwarded-proto": "https",
      host: "localhost:3000",
    });
    expect(origemDoSite(h)).toBe("https://algo.ngrok-free.dev");
    expect(urlDeVolta(origemDoSite(h))).toBe("https://algo.ngrok-free.dev/api/auth/google/callback");
  });

  it("direto no computador: o Host, em http", () => {
    expect(origemDoSite(cab({ host: "localhost:3000" }))).toBe("http://localhost:3000");
  });

  it("lista de valores: vale o primeiro", () => {
    const h = cab({ "x-forwarded-host": "a.exemplo.com, b.exemplo.com", "x-forwarded-proto": "https, http" });
    expect(origemDoSite(h)).toBe("https://a.exemplo.com");
  });

  it("APP_URL, quando definido, manda (e a barra final não atrapalha)", () => {
    expect(origemDoSite(cab({ host: "outro:1" }), "https://vistos.concept.com.br/")).toBe(
      "https://vistos.concept.com.br",
    );
  });

  it("protocolo estranho vira http, e host com lixo é recusado", () => {
    expect(origemDoSite(cab({ host: "localhost:3000", "x-forwarded-proto": "javascript" }))).toBe(
      "http://localhost:3000",
    );
    for (const ruim of ["evil.com/x", "a b", "evil.com@outro.com", "<script>"]) {
      expect(() => origemDoSite(cab({ "x-forwarded-host": ruim }))).toThrow();
    }
    expect(() => origemDoSite(cab({}))).toThrow();
  });
});

describe("urlDoGoogle", () => {
  it("leva o que a proteção do fluxo exige", () => {
    const u = new URL(
      urlDoGoogle({
        clientId: "123.apps.googleusercontent.com",
        redirectUri: "http://localhost:3000/api/auth/google/callback",
        state: "estado-1",
        nonce: "nonce-1",
        desafio: "desafio-1",
      }),
    );
    expect(u.origin + u.pathname).toBe("https://accounts.google.com/o/oauth2/v2/auth");
    expect(Object.fromEntries(u.searchParams)).toEqual({
      client_id: "123.apps.googleusercontent.com",
      redirect_uri: "http://localhost:3000/api/auth/google/callback",
      response_type: "code",
      scope: "openid email profile",
      state: "estado-1",
      nonce: "nonce-1",
      code_challenge: "desafio-1",
      code_challenge_method: "S256",
      prompt: "select_account",
    });
  });
});

describe("cookie do login em andamento", () => {
  const bom = { state: "s", nonce: "n", verificador: "v", destino: "/processos" };

  it("lê um estado válido", () => {
    expect(lerEstado(JSON.stringify(bom))).toEqual(bom);
  });

  it.each([
    undefined,
    "",
    "não é json",
    "null",
    JSON.stringify({ ...bom, state: "" }),
    JSON.stringify({ ...bom, nonce: 7 }),
    JSON.stringify({ state: "s" }),
  ])("estado inválido vira null (%s)", (bruto) => {
    expect(lerEstado(bruto as string | undefined)).toBeNull();
  });
});

describe("mensagens de erro do login", () => {
  it("traduz os motivos conhecidos e ignora o resto (nem 'constructor' vaza)", () => {
    expect(mensagemDoErroGoogle("google_sem_acesso")).toMatch(/não tem acesso/);
    expect(mensagemDoErroGoogle("constructor")).toBeUndefined();
    expect(mensagemDoErroGoogle("<script>")).toBeUndefined();
    expect(mensagemDoErroGoogle(null)).toBeUndefined();
    expect(Object.keys(ERROS_DO_GOOGLE).every((k) => k.startsWith("google_"))).toBe(true);
  });
});
