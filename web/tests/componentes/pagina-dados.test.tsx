/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";

import { PaginaDados } from "@/components/passaporte/paginas";
import type { LinhaPainel, ProcessoDetalhe } from "@/lib/tipos";

jest.mock("motion/react", () => ({ motion: new Proxy({}, { get: () => "div" }) }));

const linha = {
  processo_id: 12,
  tipo: "PASS",
  situacao: "Cadastro",
  cliente_id: 3,
  cliente: "Joana Prado Lins",
  telefone: "41999990000",
  grupo: null,
} as unknown as LinhaPainel;
const detalhe = {
  id: 12,
  tipo: "PASS",
  criado_em: "2026-01-02T10:00:00Z",
  atualizado_em: "2026-01-03T10:00:00Z",
  observacao: null,
  solicitantes: [],
} as unknown as ProcessoDetalhe;

describe("Página de dados do processo: e-mail do cliente", () => {
  it("mostra o e-mail como link mailto (é com ele que se entra no site do consulado)", () => {
    render(<PaginaDados linha={linha} detalhe={detalhe} emailCliente="joana@exemplo.com" />);
    expect(screen.getByText("E-mail")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "joana@exemplo.com" });
    expect(link).toHaveAttribute("href", "mailto:joana@exemplo.com");
  });

  it("cliente sem e-mail (ou ficha indisponível): travessão, sem link", () => {
    render(<PaginaDados linha={linha} detalhe={detalhe} emailCliente={null} />);
    expect(screen.getByText("E-mail")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });
});
