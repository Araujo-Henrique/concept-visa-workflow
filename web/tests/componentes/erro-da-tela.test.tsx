/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ErroDaTela from "@/app/(app)/error";

describe("tela de erro da área logada", () => {
  it("explica o problema, tenta de novo e mostra o código para achar no log", async () => {
    const retry = jest.fn();
    const erro = Object.assign(new Error("A API teve um erro interno"), { digest: "abc123" });
    render(<ErroDaTela error={erro} retry={retry} />);
    expect(screen.getByRole("heading", { name: "Turbulência no caminho" })).toBeInTheDocument();
    expect(screen.getByText("código: abc123")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Tentar de novo/ }));
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
