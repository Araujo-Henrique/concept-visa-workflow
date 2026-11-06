/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";

import { moverCartao, Quadro, type Coluna } from "@/components/processos/quadro";
import { lerFiltros } from "@/lib/processos";
import type { LinhaPainel } from "@/lib/tipos";

jest.mock("@/app/acoes/processos", () => ({ mudarSituacao: jest.fn() }));

const processo = (id: number, situacao: string) =>
  ({
    processo_id: id,
    tipo: "OBT",
    situacao,
    cliente: `Cliente ${id}`,
    n_solicitantes: 1,
    resultado_geral: "Processando",
    consulado: "SP",
    data_casv: null,
    data_entrevista: null,
  }) as unknown as LinhaPainel;

const colunas: Coluna[] = [
  { situacao: "Cadastro", itens: [processo(1, "Cadastro"), processo(2, "Cadastro")], total: 2 },
  { situacao: "Pago", itens: [], total: 0 },
  { situacao: "Concluido", itens: [processo(9, "Concluido")], total: 3300 },
];

describe("movimento otimista do quadro", () => {
  it("tira o card da coluna de origem, põe no topo do destino e acerta os totais", () => {
    const depois = moverCartao(colunas, { processo: processo(1, "Cadastro"), de: "Cadastro", para: "Pago" });
    expect(depois[0].itens.map((p) => p.processo_id)).toEqual([2]);
    expect(depois[0].total).toBe(1);
    expect(depois[1].itens[0]).toMatchObject({ processo_id: 1, situacao: "Pago" });
    expect(depois[1].total).toBe(1);
    expect(depois[2]).toBe(colunas[2]); // colunas não envolvidas nem são copiadas
  });

  it("não altera as colunas originais (o React precisa de um estado novo)", () => {
    moverCartao(colunas, { processo: processo(1, "Cadastro"), de: "Cadastro", para: "Pago" });
    expect(colunas[0].itens).toHaveLength(2);
  });
});

describe("quadro", () => {
  it("mostra o total real da coluna e leva o resto para a tabela filtrada", () => {
    render(<Quadro colunas={colunas} filtros={lerFiltros({ visao: "quadro" })} podeMover />);
    const link = screen.getByRole("link", { name: /e mais 3\.299/ });
    expect(link).toHaveAttribute("href", "/processos?situacao=Concluido");
  });

  it("leitor não vê a alça de arrastar", () => {
    render(<Quadro colunas={colunas} filtros={lerFiltros({})} podeMover={false} />);
    expect(screen.queryByRole("button", { name: /Mover o processo/ })).not.toBeInTheDocument();
  });

  it("coluna vazia fica recolhida numa faixa, para as cheias caberem na tela", () => {
    render(<Quadro colunas={colunas} filtros={lerFiltros({})} podeMover />);
    expect(screen.getByRole("region", { name: "Pago: nenhum processo" })).toBeInTheDocument();
    expect(screen.queryByText("Solte um processo aqui")).not.toBeInTheDocument();
  });
});
