/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Estrutura } from "@/components/shell/estrutura";
import type { Usuario } from "@/lib/tipos";

const mockPush = jest.fn();
const mockBuscar = jest.fn();
jest.mock("next/navigation", () => ({ usePathname: () => "/", useRouter: () => ({ push: mockPush }) }));
jest.mock("@/app/acoes/auth", () => ({ sair: jest.fn(), entrar: jest.fn() }));
jest.mock("@/app/acoes/processos", () => ({ buscar: (...args: unknown[]) => mockBuscar(...args) }));

beforeEach(() => {
  mockPush.mockClear();
  mockBuscar.mockReset().mockResolvedValue([]);
});

const pessoa = (perfil: Usuario["perfil"]): Usuario => ({
  id: 1,
  nome: "Pessoa Teste",
  email: "pessoa@exemplo.com",
  ativo: true,
  perfil,
});

function menuPrincipal() {
  // o menu do celular fica fechado (Sheet); só o da lateral está montado
  return within(screen.getByRole("navigation", { name: "Principal" }));
}

describe("menu lateral", () => {
  it("admin vê Usuários; atendente e leitor não", () => {
    const { unmount } = render(
      <Estrutura usuario={pessoa("admin")}>
        <p>conteúdo</p>
      </Estrutura>,
    );
    expect(menuPrincipal().getByText("Usuários")).toBeInTheDocument();
    unmount();

    for (const perfil of ["atendente", "leitor"] as const) {
      const r = render(<Estrutura usuario={pessoa(perfil)}>x</Estrutura>);
      expect(menuPrincipal().queryByText("Usuários")).not.toBeInTheDocument();
      r.unmount();
    }
  });

  it("marca a página atual", () => {
    render(<Estrutura usuario={pessoa("leitor")}>x</Estrutura>);
    const menu = menuPrincipal();
    expect(menu.getByRole("link", { name: "Início" })).toHaveAttribute("aria-current", "page");
    expect(menu.getByRole("link", { name: "Processos" })).not.toHaveAttribute("aria-current");
    expect(menu.getByRole("link", { name: "Clientes" })).toBeInTheDocument();
    expect(menu.getByRole("link", { name: "Agenda" })).toBeInTheDocument();
  });

  it("todas as telas prontas: admin tem o link de Usuários e nada 'em breve'", () => {
    render(<Estrutura usuario={pessoa("admin")}>x</Estrutura>);
    const menu = menuPrincipal();
    expect(menu.getByRole("link", { name: "Usuários" })).toHaveAttribute("href", "/usuarios");
    expect(menu.queryByText("em breve")).not.toBeInTheDocument();
  });

  it("a busca abre com Ctrl+K", async () => {
    render(<Estrutura usuario={pessoa("leitor")}>x</Estrutura>);
    await userEvent.keyboard("{Control>}k{/Control}");
    expect(await screen.findByPlaceholderText("Nº do processo ou nome do cliente…")).toBeInTheDocument();
  });
});

describe("busca no celular", () => {
  const resultado = {
    processo_id: 7,
    tipo: "OBT",
    cliente: "Bruno Tavares",
    situacao: "Processando",
    n_solicitantes: 1,
  };

  it("a lupa fica na barra de cima: um toque abre a busca, sem abrir o menu antes", async () => {
    render(<Estrutura usuario={pessoa("leitor")}>x</Estrutura>);
    await userEvent.click(screen.getByRole("button", { name: "Buscar processo" }));
    expect(await screen.findByPlaceholderText("Nº do processo ou nome do cliente…")).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Menu" })).not.toBeInTheDocument();
  });

  it("escolher um resultado abre o processo", async () => {
    mockBuscar.mockResolvedValue([resultado]);
    render(<Estrutura usuario={pessoa("leitor")}>x</Estrutura>);
    await userEvent.click(screen.getByRole("button", { name: "Buscar processo" }));
    await userEvent.type(await screen.findByPlaceholderText("Nº do processo ou nome do cliente…"), "Bruno");
    await userEvent.click(await screen.findByText("Bruno Tavares"));
    expect(mockPush).toHaveBeenCalledWith("/processos/7");
  });

  it("buscando pelo menu ☰, o resultado FECHA o menu (antes ele ficava por cima da página)", async () => {
    mockBuscar.mockResolvedValue([resultado]);
    render(<Estrutura usuario={pessoa("leitor")}>x</Estrutura>);
    await userEvent.click(screen.getByRole("button", { name: "Abrir menu" }));
    const menu = await screen.findByRole("dialog", { name: "Menu" });
    await userEvent.click(within(menu).getByRole("button", { name: /Buscar…/ }));
    await userEvent.type(await screen.findByPlaceholderText("Nº do processo ou nome do cliente…"), "Bruno");
    await userEvent.click(await screen.findByText("Bruno Tavares"));
    expect(mockPush).toHaveBeenCalledWith("/processos/7");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Menu" })).not.toBeInTheDocument());
  });

  it("a dica 'Ctrl K' só aparece a partir do tamanho de computador (no celular não existe teclado)", () => {
    render(<Estrutura usuario={pessoa("leitor")}>x</Estrutura>);
    const dica = screen.getByText("Ctrl K");
    expect(dica).toHaveClass("hidden", "lg:inline");
  });
});
