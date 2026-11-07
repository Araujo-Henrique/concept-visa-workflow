/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renomearSolicitante } from "@/app/acoes/processos";
import { PaginaPessoas } from "@/components/passaporte/pagina-pessoas";
import type { Solicitante } from "@/lib/tipos";

jest.mock("@/app/acoes/processos", () => ({
  renomearSolicitante: jest.fn().mockResolvedValue({ ok: true, dados: null }),
}));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

const pessoa = (id: number, nome: string, titular = false): Solicitante => ({
  id,
  processo_id: 1,
  nome,
  titular,
  resultado: "Processando",
  formularios: [],
});

function renderizar(escrever: boolean) {
  render(
    <PaginaPessoas
      processoId={1}
      solicitantes={[pessoa(1, "Renata Vasconcelos", true), pessoa(2, "Solicitante 2")]}
      comDs160={false}
      statusDs={["Pendente"]}
      permissoes={{ escrever, apagar: false }}
    />,
  );
}

describe("nome do solicitante", () => {
  it("atendente renomeia na própria linha: Enter salva", async () => {
    renderizar(true);
    await userEvent.click(screen.getByRole("button", { name: "Editar o nome de Solicitante 2" }));
    const campo = screen.getByRole("textbox", { name: "Novo nome de Solicitante 2" });
    await userEvent.clear(campo);
    await userEvent.type(campo, "Pedro Vasconcelos{Enter}");
    expect(renomearSolicitante).toHaveBeenCalledWith(2, "Pedro Vasconcelos");
  });

  it("Esc cancela sem chamar a API", async () => {
    (renomearSolicitante as jest.Mock).mockClear();
    renderizar(true);
    await userEvent.click(screen.getByRole("button", { name: "Editar o nome de Solicitante 2" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Novo nome de Solicitante 2" }), "xx{Escape}");
    expect(renomearSolicitante).not.toHaveBeenCalled();
    expect(screen.getByText("Solicitante 2")).toBeInTheDocument();
  });

  it("leitor só vê o nome, sem lápis", () => {
    renderizar(false);
    expect(screen.queryByRole("button", { name: /Editar o nome/ })).not.toBeInTheDocument();
  });
});
