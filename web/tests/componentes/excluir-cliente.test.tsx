/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { excluirCliente } from "@/app/acoes/clientes";
import { ExcluirCliente, nomeConfere } from "@/components/clientes/controles";
import type { Cliente } from "@/lib/tipos";

const mockReplace = jest.fn();
jest.mock("next/navigation", () => ({ useRouter: () => ({ replace: mockReplace, push: jest.fn() }) }));
jest.mock("@/app/acoes/clientes", () => ({
  excluirCliente: jest.fn(),
  criarCliente: jest.fn(),
  editarCliente: jest.fn(),
}));
jest.mock("sonner", () => ({ toast: { success: jest.fn() } }));

const excluir = excluirCliente as jest.MockedFunction<typeof excluirCliente>;
const cliente = { id: 7, nome: "Joana Prado Lins" } as Cliente;

describe("Excluir cliente", () => {
  beforeEach(() => jest.clearAllMocks());

  it("o nome confere sem diferenciar maiúsculas e espaços", () => {
    expect(nomeConfere("  joana   prado lins ", "Joana Prado Lins")).toBe(true);
    expect(nomeConfere("Joana", "Joana Prado Lins")).toBe(false);
    expect(nomeConfere("", "")).toBe(false);
  });

  it("diz quantos processos saem junto e só exclui depois de digitar o nome", async () => {
    excluir.mockResolvedValue({ ok: true, dados: null });
    render(<ExcluirCliente cliente={cliente} processos={2} />);
    await userEvent.click(screen.getByRole("button", { name: /Excluir/ }));
    expect(screen.getByRole("dialog")).toHaveTextContent("os 2 processos");
    const confirmar = screen.getByRole("button", { name: "Excluir definitivamente" });
    expect(confirmar).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/digite o nome/), "Joana Prado");
    expect(confirmar).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/digite o nome/), " lins");
    await userEvent.click(confirmar);
    expect(excluir).toHaveBeenCalledWith(7);
    expect(mockReplace).toHaveBeenCalledWith("/clientes");
  });

  it("erro da API aparece no diálogo e a pessoa fica na página", async () => {
    excluir.mockResolvedValue({ ok: false, erro: "Seu perfil não permite esta ação" });
    render(<ExcluirCliente cliente={cliente} processos={1} />);
    await userEvent.click(screen.getByRole("button", { name: /Excluir/ }));
    expect(screen.getByRole("dialog")).toHaveTextContent("o processo dele");
    await userEvent.type(screen.getByLabelText(/digite o nome/), "Joana Prado Lins");
    await userEvent.click(screen.getByRole("button", { name: "Excluir definitivamente" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("não permite");
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
