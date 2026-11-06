import { entrar, sair } from "@/app/acoes/auth";

// A ação de login roda no servidor do Next: troca e-mail e senha por um token e o guarda num cookie httpOnly.
const mockCookies = { set: jest.fn(), delete: jest.fn() };
jest.mock("next/headers", () => ({ cookies: async () => mockCookies }));
jest.mock("next/navigation", () => ({
  redirect: (destino: string) => {
    throw new Error(`REDIRECT:${destino}`);
  },
}));

const resposta = (corpo: unknown, init: ResponseInit = {}) => new Response(JSON.stringify(corpo), init);
const form = (email: string, senha: string) => {
  const f = new FormData();
  f.set("email", email);
  f.set("senha", senha);
  return f;
};

let fetchMock: jest.SpyInstance;
const TOKEN = { access_token: "jwt-secreto", expira_em_minutos: 30 };

beforeEach(() => {
  process.env.API_URL = "http://api.teste:8000";
  fetchMock = jest.spyOn(global, "fetch");
});

afterEach(() => {
  jest.restoreAllMocks();
  mockCookies.set.mockReset();
  mockCookies.delete.mockReset();
});

describe("entrar: validação antes de falar com a API", () => {
  it("recusa e-mail inválido sem chamar a API", async () => {
    expect(await entrar(undefined, form("isso-nao-e-email", "qualquer"))).toEqual({
      erro: "Informe um e-mail válido.",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("recusa senha vazia sem chamar a API", async () => {
    expect(await entrar(undefined, form("ana@exemplo.com", ""))).toEqual({ erro: "Informe a senha." });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("entrar: o que a pessoa vê quando algo falha", () => {
  it("API_URL ausente: diz o que configurar, em vez de culpar a API", async () => {
    delete process.env.API_URL;
    const r = await entrar(undefined, form("ana@exemplo.com", "senha-longa-123"));
    expect(r?.erro).toMatch(/API_URL/);
    expect(r?.erro).not.toMatch(/ligada/);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("API fora do ar: pergunta se está ligada", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));
    const r = await entrar(undefined, form("ana@exemplo.com", "senha-longa-123"));
    expect(r?.erro).toMatch(/ligada/);
    expect(mockCookies.set).not.toHaveBeenCalled();
  });

  it("401: mensagem única para e-mail ou senha errados (não revela qual)", async () => {
    fetchMock.mockResolvedValue(resposta({ detail: "E-mail ou senha incorretos" }, { status: 401 }));
    expect(await entrar(undefined, form("ana@exemplo.com", "errada"))).toEqual({
      erro: "E-mail ou senha incorretos.",
    });
    expect(mockCookies.set).not.toHaveBeenCalled();
  });

  it("outro erro da API usa o texto dela ou a mensagem padrão do status", async () => {
    fetchMock.mockResolvedValue(new Response("falhou", { status: 503 }));
    const r = await entrar(undefined, form("ana@exemplo.com", "senha-longa-123"));
    expect(r?.erro).toMatch(/indisponível/);
    expect(mockCookies.set).not.toHaveBeenCalled();
  });
});

describe("entrar: login com sucesso", () => {
  beforeEach(() => {
    fetchMock
      .mockResolvedValueOnce(resposta(TOKEN))
      .mockResolvedValueOnce(resposta({ nome: "Ana Maria Souza", perfil: "atendente" }));
  });

  it("guarda o token num cookie httpOnly com a mesma validade do token", async () => {
    await entrar(undefined, form("ana@exemplo.com", "senha-longa-123"));
    expect(mockCookies.set).toHaveBeenCalledTimes(1);
    const [nome, valor, opcoes] = mockCookies.set.mock.calls[0];
    expect(nome).toBe("cv_sessao");
    expect(valor).toBe("jwt-secreto");
    expect(opcoes).toMatchObject({ httpOnly: true, sameSite: "lax", path: "/", maxAge: 30 * 60 });
  });

  it("devolve só o primeiro nome para a boas-vindas, e nunca o token", async () => {
    const r = await entrar(undefined, form("ana@exemplo.com", "senha-longa-123"));
    expect(r).toEqual({ ok: true, primeiroNome: "Ana" });
    expect(JSON.stringify(r)).not.toContain("jwt-secreto");
  });

  it("manda e-mail e senha para a rota de login da API, e o token na busca do nome", async () => {
    await entrar(undefined, form("ana@exemplo.com", "senha-longa-123"));
    const [urlLogin, initLogin] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(urlLogin).toBe("http://api.teste:8000/auth/login");
    expect(JSON.parse(initLogin.body as string)).toEqual({
      email: "ana@exemplo.com",
      senha: "senha-longa-123",
    });
    const [urlEu, initEu] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(urlEu).toBe("http://api.teste:8000/auth/eu");
    expect((initEu.headers as Record<string, string>).Authorization).toBe("Bearer jwt-secreto");
  });
});

describe("entrar: o nome é só um enfeite", () => {
  it("se a busca do nome falhar, o login continua valendo", async () => {
    fetchMock.mockResolvedValueOnce(resposta(TOKEN)).mockRejectedValueOnce(new TypeError("fetch failed"));
    const r = await entrar(undefined, form("ana@exemplo.com", "senha-longa-123"));
    expect(r).toEqual({ ok: true, primeiroNome: undefined });
    expect(mockCookies.set).toHaveBeenCalledTimes(1);
  });
});

describe("sair", () => {
  it("apaga o cookie de sessão e volta ao login", async () => {
    await expect(sair()).rejects.toThrow("REDIRECT:/login");
    expect(mockCookies.delete).toHaveBeenCalledWith("cv_sessao");
  });
});
