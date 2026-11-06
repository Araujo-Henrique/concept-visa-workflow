import { apiEnviar, apiGet, apiLista, montarCaminho, urlDaApi } from "@/lib/api";
import { ErroApi } from "@/lib/erros";

// A camada que fala com a API Python. O token sai do cookie httpOnly (mock de next/headers) e o
// redirecionamento do Next (que lança uma exceção) vira um erro que o teste consegue ler.
const mockCookies = { get: jest.fn() };
jest.mock("next/headers", () => ({ cookies: async () => mockCookies }));
jest.mock("next/navigation", () => ({
  redirect: (destino: string) => {
    throw new Error(`REDIRECT:${destino}`);
  },
}));

const resposta = (corpo: unknown, init: ResponseInit = {}) => new Response(JSON.stringify(corpo), init);

let fetchMock: jest.SpyInstance;
const ultimaChamada = () => fetchMock.mock.calls.at(-1) as [string, RequestInit];

beforeEach(() => {
  process.env.API_URL = "http://api.teste:8000/";
  mockCookies.get.mockReturnValue({ value: "token-abc" });
  fetchMock = jest.spyOn(global, "fetch");
});

afterEach(() => {
  jest.restoreAllMocks();
  mockCookies.get.mockReset();
});

describe("urlDaApi", () => {
  it("tira a barra final, para não duplicar na montagem do endereço", () => {
    expect(urlDaApi()).toBe("http://api.teste:8000");
  });

  it("sem API_URL, falha dizendo o que configurar", () => {
    delete process.env.API_URL;
    expect(() => urlDaApi()).toThrow(/API_URL/);
  });
});

describe("montarCaminho", () => {
  it("ignora parâmetros vazios, nulos e indefinidos, mas mantém 0 e false", () => {
    expect(montarCaminho("/painel", { tipo: "OBT", situacao: "", cliente: null, x: undefined })).toBe(
      "/painel?tipo=OBT",
    );
    expect(montarCaminho("/painel", { offset: 0, ativo: false })).toBe("/painel?offset=0&ativo=false");
    expect(montarCaminho("/painel")).toBe("/painel");
  });

  it("codifica o texto digitado", () => {
    expect(montarCaminho("/painel", { cliente: "ana & bia" })).toBe("/painel?cliente=ana+%26+bia");
  });
});

describe("chamada autenticada", () => {
  it("envia o token do cookie no cabeçalho Authorization e nunca usa cache", async () => {
    fetchMock.mockResolvedValue(resposta({ ok: true }));
    await apiGet("/auth/eu");
    const [url, init] = ultimaChamada();
    expect(url).toBe("http://api.teste:8000/auth/eu");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer token-abc");
    expect(init.cache).toBe("no-store");
  });

  it("sem cookie de sessão nem chama a API: vai para o login", async () => {
    mockCookies.get.mockReturnValue(undefined);
    await expect(apiGet("/painel")).rejects.toThrow("REDIRECT:/login");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("401 da API (token vencido ou usuário desativado) manda para o login avisando que expirou", async () => {
    fetchMock.mockResolvedValue(resposta({ detail: "Faça login para acessar" }, { status: 401 }));
    await expect(apiGet("/painel")).rejects.toThrow("REDIRECT:/login?expirou=1");
  });

  it("erro de regra da API vira ErroApi com o texto da própria API", async () => {
    fetchMock.mockResolvedValue(resposta({ detail: "Informe o motivo para reabrir" }, { status: 422 }));
    const erro = await apiGet("/x").catch((e) => e);
    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro).toMatchObject({ status: 422, message: "Informe o motivo para reabrir" });
  });

  it("resposta de erro sem corpo JSON cai na mensagem padrão do status", async () => {
    fetchMock.mockResolvedValue(new Response("<html>erro</html>", { status: 403 }));
    await expect(apiGet("/x")).rejects.toMatchObject({
      status: 403,
      message: "Seu perfil não permite esta ação.",
    });
  });

  it("API fora do ar vira ErroApi 503 (e não um erro técnico de rede)", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));
    await expect(apiGet("/x")).rejects.toMatchObject({ status: 503 });
  });

  it("API_URL ausente é erro de configuração, e não 'API fora do ar'", async () => {
    delete process.env.API_URL;
    const erro = (await apiGet("/x").catch((e: unknown) => e)) as Error;
    expect(erro).not.toBeInstanceOf(ErroApi);
    expect(erro.message).toMatch(/API_URL/);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("apiLista", () => {
  it("devolve os itens e o total do cabeçalho X-Total-Count", async () => {
    fetchMock.mockResolvedValue(resposta([{ id: 1 }, { id: 2 }], { headers: { "X-Total-Count": "57" } }));
    expect(await apiLista("/painel", { limit: 2 })).toEqual({ itens: [{ id: 1 }, { id: 2 }], total: 57 });
    expect(ultimaChamada()[0]).toBe("http://api.teste:8000/painel?limit=2");
  });

  it("total é null quando a rota não informa", async () => {
    fetchMock.mockResolvedValue(resposta([]));
    expect((await apiLista("/clientes")).total).toBeNull();
  });
});

describe("apiEnviar", () => {
  it("manda o corpo como JSON com o método pedido", async () => {
    fetchMock.mockResolvedValue(resposta({ id: 9 }, { status: 201 }));
    expect(await apiEnviar("POST", "/clientes", { nome: "Ana" })).toEqual({ id: 9 });
    const [, init] = ultimaChamada();
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ nome: "Ana" }));
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("204 (sem conteúdo) devolve null", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    expect(await apiEnviar("DELETE", "/clientes/1")).toBeNull();
  });

  it("sem corpo, não declara Content-Type", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await apiEnviar("DELETE", "/clientes/1");
    expect((ultimaChamada()[1].headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });
});
