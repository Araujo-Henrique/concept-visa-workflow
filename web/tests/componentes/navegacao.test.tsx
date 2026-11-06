/**
 * @jest-environment jsdom
 */
import { render, screen, within } from "@testing-library/react";

import { Estrutura } from "@/components/shell/estrutura";
import type { Usuario } from "@/lib/tipos";

jest.mock("next/navigation", () => ({ usePathname: () => "/" }));
jest.mock("@/app/acoes/auth", () => ({ sair: jest.fn(), entrar: jest.fn() }));

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

  it("marca a página atual e mostra as próximas telas como 'em breve', sem link", () => {
    render(<Estrutura usuario={pessoa("leitor")}>x</Estrutura>);
    const menu = menuPrincipal();
    expect(menu.getByRole("link", { name: "Início" })).toHaveAttribute("aria-current", "page");
    expect(menu.queryByRole("link", { name: /Processos/ })).not.toBeInTheDocument();
    expect(menu.getAllByText("em breve").length).toBeGreaterThan(0);
  });
});
