/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { editarProcesso } from "@/app/acoes/processos";
import { FaixaDespacho } from "@/components/passaporte/despacho";

jest.mock("@/app/acoes/processos", () => ({ editarProcesso: jest.fn() }));
jest.mock("sonner", () => ({ toast: { success: jest.fn() } }));

const editar = editarProcesso as jest.MockedFunction<typeof editarProcesso>;
const base = { processoId: 7, prazo: "2026-11-05", rastreio: null, hoje: "2026-11-07" };

describe("Faixa do despacho (REN)", () => {
  beforeEach(() => editar.mockReset());

  it("prazo vencido e nada despachado: atrasado, com o botão para marcar", () => {
    render(<FaixaDespacho {...base} despachadoEm={null} podeMarcar />);
    expect(screen.getByText("Atrasado")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Marcar como despachado/ })).toBeInTheDocument();
  });

  it("marcar grava a data de hoje e o rastreio digitado", async () => {
    editar.mockResolvedValue({ ok: true, dados: null });
    render(<FaixaDespacho {...base} despachadoEm={null} podeMarcar />);
    await userEvent.click(screen.getByRole("button", { name: /Marcar como despachado/ }));
    await userEvent.type(screen.getByLabelText("Código de rastreio"), "BR123");
    await userEvent.click(screen.getByRole("button", { name: "Registrar despacho" }));
    expect(editar).toHaveBeenCalledWith("REN", 7, { despachado_em: "2026-11-07", codigo_rastreio: "BR123" });
  });

  it("não aceita data no futuro", async () => {
    render(<FaixaDespacho {...base} despachadoEm={null} podeMarcar />);
    await userEvent.click(screen.getByRole("button", { name: /Marcar como despachado/ }));
    const data = screen.getByLabelText("Despachado em");
    await userEvent.clear(data);
    await userEvent.type(data, "2026-12-01");
    await userEvent.click(screen.getByRole("button", { name: "Registrar despacho" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("não pode ser no futuro");
    expect(editar).not.toHaveBeenCalled();
  });

  it("já despachado: mostra a data e não oferece o botão; leitor não vê o botão", () => {
    const { unmount } = render(<FaixaDespacho {...base} despachadoEm="2026-11-04" podeMarcar />);
    expect(screen.getByText(/Despachado em 04\/11\/2026/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Marcar/ })).not.toBeInTheDocument();
    unmount();
    render(<FaixaDespacho {...base} despachadoEm={null} podeMarcar={false} />);
    expect(screen.queryByRole("button", { name: /Marcar/ })).not.toBeInTheDocument();
  });
});
