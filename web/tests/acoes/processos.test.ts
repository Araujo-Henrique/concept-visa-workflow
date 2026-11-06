import { buscar, mudarResultado, mudarSituacao } from "@/app/acoes/processos";
import { apiEnviar, apiLista } from "@/lib/api";
import { ErroApi } from "@/lib/erros";

// As ações chamadas pelas telas. Quem decide se a pessoa pode é a API: aqui só se confere o que é enviado
// e como o erro volta para a tela.
jest.mock("@/lib/api", () => ({ apiEnviar: jest.fn(), apiLista: jest.fn() }));
const mockRefresh = jest.fn();
jest.mock("next/cache", () => ({ refresh: () => mockRefresh() }));

const enviar = apiEnviar as jest.Mock;
const listar = apiLista as jest.Mock;

afterEach(() => jest.resetAllMocks());

describe("mudarSituacao", () => {
  it("envia a situação para a rota do workflow e atualiza a tela", async () => {
    enviar.mockResolvedValue({ id: 1, tipo: "situacao_alterada" });
    const r = await mudarSituacao(12, "Pago");
    expect(enviar).toHaveBeenCalledWith("POST", "/processos/12/situacao", { situacao: "Pago" });
    expect(r).toEqual({ ok: true, dados: { id: 1, tipo: "situacao_alterada" } });
    expect(mockRefresh).toHaveBeenCalledTimes(1);
  });

  it("limpa os espaços do motivo e o envia", async () => {
    enviar.mockResolvedValue({});
    await mudarSituacao(12, "Processando", "  Cliente vai tentar de novo  ");
    expect(enviar).toHaveBeenCalledWith("POST", "/processos/12/situacao", {
      situacao: "Processando",
      motivo: "Cliente vai tentar de novo",
    });
  });

  it("motivo só com espaços não é enviado (a API pede o motivo de verdade ao reabrir)", async () => {
    enviar.mockResolvedValue({});
    await mudarSituacao(12, "Pago", "   ");
    expect(enviar.mock.calls[0][2]).toEqual({ situacao: "Pago" });
  });

  it("regra recusada pela API volta como texto para a tela, sem atualizar", async () => {
    enviar.mockRejectedValue(new ErroApi(422, "Informe o motivo para reabrir um processo concluído"));
    const r = await mudarSituacao(12, "Processando");
    expect(r).toEqual({ ok: false, erro: "Informe o motivo para reabrir um processo concluído" });
    expect(mockRefresh).not.toHaveBeenCalled();
  });

  it("erro inesperado (como o redirect de sessão expirada) não é engolido", async () => {
    enviar.mockRejectedValue(new Error("REDIRECT:/login?expirou=1"));
    await expect(mudarSituacao(12, "Pago")).rejects.toThrow("REDIRECT");
  });
});

describe("mudarResultado", () => {
  it("altera o resultado do solicitante e atualiza a tela", async () => {
    enviar.mockResolvedValue({});
    expect(await mudarResultado(5, "Aprovado")).toEqual({ ok: true, dados: {} });
    expect(enviar).toHaveBeenCalledWith("PATCH", "/solicitantes/5", { resultado: "Aprovado" });
    expect(mockRefresh).toHaveBeenCalledTimes(1);
  });

  it("perfil sem permissão: a mensagem da API chega à tela", async () => {
    enviar.mockRejectedValue(new ErroApi(403, "Seu perfil não permite esta ação"));
    expect(await mudarResultado(5, "Aprovado")).toEqual({
      ok: false,
      erro: "Seu perfil não permite esta ação",
    });
  });
});

describe("buscar (Ctrl+K)", () => {
  const linha = {
    processo_id: 7,
    tipo: "OBT",
    cliente: "Ana",
    situacao: "Pago",
    n_solicitantes: 2,
    extra: "x",
  };

  it("termo curto demais não consulta a API", async () => {
    expect(await buscar("a")).toEqual([]);
    expect(await buscar("  ")).toEqual([]);
    expect(listar).not.toHaveBeenCalled();
  });

  it("número é procura por processo (um resultado); aceita o # na frente", async () => {
    listar.mockResolvedValue({ itens: [linha], total: 1 });
    await buscar("#7");
    expect(listar).toHaveBeenCalledWith("/painel", { processo_id: 7, limit: 1 });
  });

  it("um único dígito vale como número de processo", async () => {
    listar.mockResolvedValue({ itens: [], total: 0 });
    await buscar("7");
    expect(listar).toHaveBeenCalledWith("/painel", { processo_id: 7, limit: 1 });
  });

  it("texto é procura por nome de cliente (até 8 resultados)", async () => {
    listar.mockResolvedValue({ itens: [linha], total: 1 });
    await buscar("  ana ");
    expect(listar).toHaveBeenCalledWith("/painel", { cliente: "ana", limit: 8 });
  });

  it("devolve só os campos que a busca mostra", async () => {
    listar.mockResolvedValue({ itens: [linha], total: 1 });
    expect(await buscar("ana")).toEqual([
      { processo_id: 7, tipo: "OBT", cliente: "Ana", situacao: "Pago", n_solicitantes: 2 },
    ]);
  });
});
