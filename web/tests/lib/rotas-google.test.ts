/** @jest-environment node */
import { GET as callback } from "@/app/api/auth/google/callback/route";
import { GET as ida } from "@/app/api/auth/google/route";
import { gravarSessao } from "@/lib/cookies-sessao";

// As duas rotas do "Entrar com o Google": ida (monta o endereço e guarda o estado) e volta (confere o state e
// entrega o código à API). O Google e a API são simulados; o que se verifica é o que sai e o que entra.
const mockCookies = { get: jest.fn() };
let mockHeaders = new Headers();
jest.mock("next/headers", () => ({ cookies: async () => mockCookies, headers: async () => mockHeaders }));
jest.mock("@/lib/cookies-sessao", () => ({ gravarSessao: jest.fn() }));

const ESTADO = {
  state: "estado-certo",
  nonce: "n".repeat(43),
  verificador: "v".repeat(43),
  destino: "/processos",
};
const resposta = (corpo: unknown, init: ResponseInit = {}) => new Response(JSON.stringify(corpo), init);
const sair = (r: Response) => new URL(r.headers.get("location")!);
const cookieGuardado = (r: Response) =>
  JSON.parse(decodeURIComponent(r.headers.get("set-cookie")!.split(";")[0]!.slice("cv_oauth=".length)));

let fetchMock: jest.SpyInstance;

beforeEach(() => {
  process.env.API_URL = "http://api.teste:8000";
  delete process.env.APP_URL;
  mockHeaders = new Headers({ host: "localhost:3000", "x-forwarded-for": "203.0.113.7" });
  fetchMock = jest.spyOn(global, "fetch");
  mockCookies.get.mockReturnValue({ value: JSON.stringify(ESTADO) });
});
afterEach(() => {
  jest.restoreAllMocks();
  jest.mocked(gravarSessao).mockReset();
  mockCookies.get.mockReset();
});

describe("ida", () => {
  it("guarda o estado num cookie httpOnly e vai para o Google com state, nonce e PKCE", async () => {
    fetchMock.mockResolvedValue(resposta({ client_id: "123.apps.googleusercontent.com" }));
    const r = await ida(new Request("http://localhost:3000/api/auth/google?de=/clientes"));

    const para = sair(r);
    expect(para.origin).toBe("https://accounts.google.com");
    expect(para.searchParams.get("client_id")).toBe("123.apps.googleusercontent.com");
    expect(para.searchParams.get("redirect_uri")).toBe("http://localhost:3000/api/auth/google/callback");
    expect(para.searchParams.get("code_challenge_method")).toBe("S256");

    const cookie = r.headers.get("set-cookie")!;
    expect(cookie).toMatch(/^cv_oauth=/);
    expect(cookie).toMatch(/HttpOnly/i);
    expect(cookie).toMatch(/SameSite=lax/i);
    expect(cookie).toMatch(/Path=\/api\/auth\/google/);
    expect(cookie).not.toMatch(/Secure/i); // http://localhost
    const guardado = cookieGuardado(r);
    expect(guardado.destino).toBe("/clientes");
    expect(guardado.state).toBe(para.searchParams.get("state"));
    expect(guardado.nonce).toBe(para.searchParams.get("nonce"));
    // o verificador fica só no cookie: ao Google vai apenas o desafio (o hash dele)
    expect(JSON.stringify([...para.searchParams.values()])).not.toContain(guardado.verificador);
  });

  it("atrás de https o cookie é Secure e a volta usa o endereço público", async () => {
    mockHeaders = new Headers({ "x-forwarded-host": "algo.ngrok-free.dev", "x-forwarded-proto": "https" });
    fetchMock.mockResolvedValue(resposta({ client_id: "c" }));
    const r = await ida(new Request("http://localhost:3000/api/auth/google"));
    expect(r.headers.get("set-cookie")).toMatch(/Secure/i);
    expect(sair(r).searchParams.get("redirect_uri")).toBe(
      "https://algo.ngrok-free.dev/api/auth/google/callback",
    );
  });

  it("destino de outro site é descartado (nada de redirecionar para fora depois do login)", async () => {
    fetchMock.mockResolvedValue(resposta({ client_id: "c" }));
    const r = await ida(new Request("http://localhost:3000/api/auth/google?de=//evil.com"));
    expect(cookieGuardado(r).destino).toBe("/");
  });

  it("repassa à API o IP de quem clicou", async () => {
    fetchMock.mockResolvedValue(resposta({ client_id: "c" }));
    await ida(new Request("http://localhost:3000/api/auth/google"));
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-Cliente-IP"]).toBe("203.0.113.7");
  });

  it("Google não configurado ou API fora do ar: volta ao login com o motivo, sem ir ao Google", async () => {
    fetchMock.mockResolvedValue(resposta({ detail: "x" }, { status: 503 }));
    let r = await ida(new Request("http://localhost:3000/api/auth/google"));
    expect(sair(r).pathname + sair(r).search).toBe("/login?erro=google_indisponivel");
    expect(r.headers.get("set-cookie")).toBeNull();

    fetchMock.mockRejectedValue(new TypeError("fetch failed"));
    r = await ida(new Request("http://localhost:3000/api/auth/google"));
    expect(sair(r).search).toBe("?erro=google_api_fora");
  });
});

describe("volta", () => {
  const url = (busca: string) => new Request(`http://localhost:3000/api/auth/google/callback?${busca}`);
  const motivo = (r: Response) => sair(r).searchParams.get("erro");

  it("tudo certo: manda o código à API, grava a sessão e vai ao destino guardado", async () => {
    fetchMock.mockResolvedValue(resposta({ access_token: "jwt-da-api", expira_em_minutos: 30 }));
    const r = await callback(url("code=codigo-do-google&state=estado-certo"));

    const [urlApi, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(urlApi).toBe("http://api.teste:8000/auth/google");
    expect(JSON.parse(init.body as string)).toEqual({
      code: "codigo-do-google",
      code_verifier: ESTADO.verificador,
      nonce: ESTADO.nonce,
      redirect_uri: "http://localhost:3000/api/auth/google/callback",
    });
    expect((init.headers as Record<string, string>)["X-Cliente-IP"]).toBe("203.0.113.7");
    expect(gravarSessao).toHaveBeenCalledWith("jwt-da-api", 30);
    expect(sair(r).pathname).toBe("/processos");
    // o cookie do login em andamento é apagado (uso único)
    expect(r.headers.get("set-cookie")).toMatch(/cv_oauth=;.*Expires=Thu, 01 Jan 1970/i);
  });

  it("state diferente (alguém tentando entregar um login alheio): recusa sem chamar a API", async () => {
    const r = await callback(url("code=x&state=outro-estado"));
    expect(motivo(r)).toBe("google_falhou");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(gravarSessao).not.toHaveBeenCalled();
  });

  it("sem state ou sem código: recusa", async () => {
    expect(motivo(await callback(url("code=x")))).toBe("google_falhou");
    expect(motivo(await callback(url("state=estado-certo")))).toBe("google_falhou");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sem o cookie do login (expirou ou outra janela): pede para tentar de novo", async () => {
    mockCookies.get.mockReturnValue(undefined);
    expect(motivo(await callback(url("code=x&state=estado-certo")))).toBe("google_expirou");
    mockCookies.get.mockReturnValue({ value: "lixo" });
    expect(motivo(await callback(url("code=x&state=estado-certo")))).toBe("google_expirou");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("a pessoa cancelou no Google, ou o Google devolveu erro", async () => {
    expect(motivo(await callback(url("error=access_denied&state=estado-certo")))).toBe("google_cancelado");
    expect(motivo(await callback(url("error=server_error&state=estado-certo")))).toBe("google_falhou");
  });

  it("e-mail não cadastrado (403): volta ao login dizendo isso, sem criar sessão", async () => {
    fetchMock.mockResolvedValue(
      resposta({ detail: "Este e-mail não tem acesso ao sistema" }, { status: 403 }),
    );
    const r = await callback(url("code=x&state=estado-certo"));
    expect(motivo(r)).toBe("google_sem_acesso");
    expect(gravarSessao).not.toHaveBeenCalled();
  });

  it("limite de tentativas (429), erro da API e API fora do ar", async () => {
    fetchMock.mockResolvedValue(resposta({ detail: "x" }, { status: 429 }));
    expect(motivo(await callback(url("code=x&state=estado-certo")))).toBe("google_muitas");
    fetchMock.mockResolvedValue(resposta({ detail: "x" }, { status: 401 }));
    expect(motivo(await callback(url("code=x&state=estado-certo")))).toBe("google_falhou");
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));
    expect(motivo(await callback(url("code=x&state=estado-certo")))).toBe("google_api_fora");
    expect(gravarSessao).not.toHaveBeenCalled();
  });

  it("nada do Google nem o código aparece na URL de volta ao login", async () => {
    const r = await callback(url("code=segredo-do-codigo&state=outro"));
    expect(r.headers.get("location")).not.toContain("segredo-do-codigo");
  });
});
