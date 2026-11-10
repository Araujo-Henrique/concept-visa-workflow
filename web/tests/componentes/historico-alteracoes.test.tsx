/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";

import { HistoricoAlteracoes } from "@/components/auditoria/historico-alteracoes";
import { apiLista } from "@/lib/api";
import { ErroApi } from "@/lib/erros";

jest.mock("@/lib/api", () => ({ apiLista: jest.fn() }));
const lista = apiLista as jest.MockedFunction<typeof apiLista>;

const base = {
  registro_id: 7,
  processo_id: null,
  cliente_id: 7,
  usuario_id: 1,
  usuario_nome: "Henrique Araujo",
  requisicao: "ab12cd34ef56",
  origem: "api",
  criado_em: "2026-11-09T17:30:00Z",
};

// componente do servidor (async): chamamos a função e renderizamos o que ela devolve
async function renderizar(filtro: { cliente_id: number } | { processo_id: number }) {
  render(await HistoricoAlteracoes({ filtro }));
}

afterEach(() => lista.mockReset());

it("pede à API o histórico do cliente e mostra quem mudou o quê", async () => {
  lista.mockResolvedValue({
    itens: [
      {
        ...base,
        id: 2,
        tabela: "clientes",
        acao: "editou",
        antes: { grupo: null },
        depois: { grupo: "Família" },
        transacao: 20,
      },
      {
        ...base,
        id: 1,
        tabela: "clientes",
        acao: "criou",
        antes: null,
        depois: { nome: "Ana" },
        transacao: 10,
      },
    ],
    total: 2,
  });
  await renderizar({ cliente_id: 7 });
  expect(lista).toHaveBeenCalledWith("/auditoria", { cliente_id: 7, limit: 200 });
  expect(screen.getByText(/Histórico de alterações · 2/)).toBeInTheDocument();
  expect(screen.getByText("Dados do cliente editados")).toBeInTheDocument();
  expect(screen.getByText("Família")).toBeInTheDocument();
  expect(screen.getByText("Cliente cadastrado: Ana")).toBeInTheDocument();
  expect(screen.getAllByText("Henrique Araujo")).toHaveLength(2);
});

it("avisa quando há mais alterações do que as mostradas", async () => {
  lista.mockResolvedValue({
    itens: [
      {
        ...base,
        id: 1,
        tabela: "clientes",
        acao: "criou",
        antes: null,
        depois: { nome: "Ana" },
        transacao: 1,
      },
    ],
    total: 350,
  });
  await renderizar({ processo_id: 3 });
  expect(screen.getByText(/Mostrando as 1 alterações mais recentes de 350/)).toBeInTheDocument();
});

it("sem alterações, diz isso", async () => {
  lista.mockResolvedValue({ itens: [], total: 0 });
  await renderizar({ processo_id: 3 });
  expect(screen.getByText(/Nenhuma alteração registrada/)).toBeInTheDocument();
});

it("erro da API não derruba a página: mostra o aviso no lugar do histórico", async () => {
  lista.mockRejectedValue(new ErroApi(503, "O servidor de dados está indisponível."));
  await renderizar({ cliente_id: 7 });
  expect(screen.getByRole("alert")).toHaveTextContent("Não consegui carregar o histórico");
});

it("outros erros (ex.: redirect de sessão expirada) seguem o fluxo do Next", async () => {
  lista.mockRejectedValue(new Error("REDIRECT:/login?expirou=1"));
  await expect(HistoricoAlteracoes({ filtro: { cliente_id: 7 } })).rejects.toThrow("REDIRECT");
});
