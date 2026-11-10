/**
 * @jest-environment jsdom
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { eliminarCliente, restaurarCliente } from "@/app/acoes/excluidos";
import { Lapides, ListaExcluidos, MOTIVO_MINIMO, quemEQuando } from "@/components/clientes/excluidos";
import type { ClienteExcluido } from "@/lib/auditoria";

jest.mock("@/app/acoes/excluidos", () => ({ restaurarCliente: jest.fn(), eliminarCliente: jest.fn() }));
// `nomeConfere` vem de controles.tsx, que também importa as ações de clientes (next/cache não roda no Jest)
jest.mock("@/app/acoes/clientes", () => ({
  excluirCliente: jest.fn(),
  criarCliente: jest.fn(),
  editarCliente: jest.fn(),
}));
jest.mock("sonner", () => ({ toast: { success: jest.fn() } }));
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

const restaurar = restaurarCliente as jest.MockedFunction<typeof restaurarCliente>;
const eliminar = eliminarCliente as jest.MockedFunction<typeof eliminarCliente>;

const ana: ClienteExcluido = {
  cliente_id: 7,
  nome: "Ana Souza",
  telefone: "41999998888",
  email: "ana@exemplo.com",
  apagado_em: "2026-11-10T12:49:00Z",
  usuario_id: 2,
  apagado_por: "Bruna Lima",
  origem: "api",
  n_processos: 2,
};

beforeEach(() => jest.clearAllMocks());

describe("lista de clientes excluídos", () => {
  it("mostra quem foi, quando, por quem e quantos processos", () => {
    render(
      <ListaExcluidos
        clientes={[ana, { ...ana, cliente_id: 8, nome: "Bia", n_processos: 0, telefone: null }]}
      />,
    );
    expect(screen.getByText("Ana Souza")).toBeInTheDocument();
    expect(screen.getByText(/\(41\) 99999-8888 · ana@exemplo.com/)).toBeInTheDocument();
    expect(
      screen.getByText(/Excluído em 10\/11\/2026 às 09:49 por Bruna Lima · 2 processos/),
    ).toBeInTheDocument();
    expect(screen.getByText(/sem processos/)).toBeInTheDocument();
  });

  it("sem excluídos, explica o que aparece ali", () => {
    render(<ListaExcluidos clientes={[]} />);
    expect(screen.getByText("Nenhum cliente excluído")).toBeInTheDocument();
  });

  it("sem usuário, diz de onde veio a exclusão", () => {
    expect(quemEQuando({ apagado_em: ana.apagado_em, apagado_por: null, origem: "banco" })).toMatch(
      /por alteração direta no banco/,
    );
  });
});

describe("restaurar", () => {
  it("chama a ação com o cliente certo e avisa o resultado", async () => {
    restaurar.mockResolvedValue({
      ok: true,
      dados: {
        cliente_id: 7,
        nome: "Ana Souza",
        processos: 2,
        pessoas: 3,
        formularios: 1,
        eventos: 4,
        vinculos: 1,
      },
    });
    render(<ListaExcluidos clientes={[ana]} />);
    await userEvent.click(screen.getByRole("button", { name: /Restaurar/ }));
    expect(restaurar).toHaveBeenCalledWith(7);
  });

  it("o erro da API (ex.: nome já em uso) aparece junto do cliente", async () => {
    restaurar.mockResolvedValue({ ok: false, erro: "Já existe outro cliente chamado 'Ana Souza'" });
    render(<ListaExcluidos clientes={[ana]} />);
    await userEvent.click(screen.getByRole("button", { name: /Restaurar/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Já existe outro cliente chamado");
  });
});

describe("eliminar de vez", () => {
  async function abrir() {
    render(<ListaExcluidos clientes={[ana]} />);
    await userEvent.click(screen.getByRole("button", { name: /Eliminar de vez/ }));
    return within(screen.getByRole("dialog"));
  }

  it("avisa que não tem volta e só libera com o nome certo E um motivo", async () => {
    const dialogo = await abrir();
    expect(dialogo.getByText(/Não existe volta/)).toBeInTheDocument();
    const confirmar = dialogo.getByRole("button", { name: "Eliminar definitivamente" });
    expect(confirmar).toBeDisabled();

    await userEvent.type(dialogo.getByLabelText(/digite o nome/), "ana souza");
    expect(confirmar).toBeDisabled(); // nome certo, sem motivo
    await userEvent.type(dialogo.getByLabelText(/Motivo/), "x".repeat(MOTIVO_MINIMO - 1));
    expect(confirmar).toBeDisabled(); // motivo curto demais
    await userEvent.type(dialogo.getByLabelText(/Motivo/), "x");
    expect(confirmar).toBeEnabled();
  });

  it("nome errado, mesmo com motivo, não libera", async () => {
    const dialogo = await abrir();
    await userEvent.type(dialogo.getByLabelText(/digite o nome/), "Outra Pessoa");
    await userEvent.type(dialogo.getByLabelText(/Motivo/), "Pedido do titular");
    expect(dialogo.getByRole("button", { name: "Eliminar definitivamente" })).toBeDisabled();
  });

  it("envia o cliente, o nome digitado e o motivo", async () => {
    eliminar.mockResolvedValue({ ok: true, dados: null });
    const dialogo = await abrir();
    await userEvent.type(dialogo.getByLabelText(/digite o nome/), "Ana Souza");
    await userEvent.type(dialogo.getByLabelText(/Motivo/), "Pedido do titular por e-mail");
    await userEvent.click(dialogo.getByRole("button", { name: "Eliminar definitivamente" }));
    expect(eliminar).toHaveBeenCalledWith(7, "Ana Souza", "Pedido do titular por e-mail");
  });

  it("erro da API aparece no diálogo e o diálogo continua aberto", async () => {
    eliminar.mockResolvedValue({ ok: false, erro: "Seu perfil não permite esta ação" });
    const dialogo = await abrir();
    await userEvent.type(dialogo.getByLabelText(/digite o nome/), "Ana Souza");
    await userEvent.type(dialogo.getByLabelText(/Motivo/), "Pedido do titular");
    await userEvent.click(dialogo.getByRole("button", { name: "Eliminar definitivamente" }));
    expect(await dialogo.findByRole("alert")).toHaveTextContent("não permite");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("cancelar limpa o que foi digitado", async () => {
    const dialogo = await abrir();
    await userEvent.type(dialogo.getByLabelText(/digite o nome/), "Ana");
    await userEvent.click(dialogo.getByRole("button", { name: "Cancelar" }));
    await userEvent.click(screen.getByRole("button", { name: /Eliminar de vez/ }));
    expect(within(screen.getByRole("dialog")).getByLabelText(/digite o nome/)).toHaveValue("");
  });
});

describe("lápides", () => {
  it("lista número, quem, quando e motivo, e nada mais", () => {
    render(
      <Lapides
        itens={[
          {
            id: 1,
            registro_id: 12,
            usuario_nome: "Henrique",
            criado_em: "2026-11-10T12:49:00Z",
            motivo: "Pedido do titular",
          },
        ]}
      />,
    );
    expect(screen.getByText("Cliente nº 12")).toBeInTheDocument();
    expect(screen.getByText(/10\/11\/2026 às 09:49 · por Henrique · Pedido do titular/)).toBeInTheDocument();
  });

  it("sem eliminações, não mostra a seção", () => {
    const { container } = render(<Lapides itens={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
