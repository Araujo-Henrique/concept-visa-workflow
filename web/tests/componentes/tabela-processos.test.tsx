/**
 * @jest-environment jsdom
 */
import { render, screen, within } from "@testing-library/react";

import { TabelaProcessos } from "@/components/processos/tabela";
import type { LinhaOBT } from "@/lib/tipos";

const obt = (extra: Partial<LinhaOBT> = {}): LinhaOBT => ({
  tipo: "OBT",
  processo_id: 1,
  situacao: "Processando",
  cliente_id: 1,
  cliente: "Joana Prado Lins",
  telefone: null,
  grupo: null,
  titular: "Joana Prado Lins",
  n_solicitantes: 1,
  solicitantes: "Joana Prado Lins",
  resultado_geral: "Processando",
  n_formularios: 1,
  atualizado_em: "2026-11-10T12:00:00Z",
  consulado: "SP",
  data_casv: "2026-12-15",
  data_entrevista: null,
  codigo_rastreio: null,
  orientacao: "Pendente",
  orientacao_data: null,
  orientacao_por: null,
  previsao_orientacao: "2026-12-01",
  ...extra,
});

describe("Tabela de processos: previsão da orientação (OBT)", () => {
  it("mostra a data prevista (2 semanas antes do CASV) sem mudar o status da orientação", () => {
    render(<TabelaProcessos linhas={[obt()]} tipo="OBT" />);
    expect(screen.getByRole("columnheader", { name: "Orientação prevista" })).toBeInTheDocument();
    const linha = within(screen.getByRole("row", { name: /Joana Prado Lins/ }));
    expect(linha.getByText("01/12/2026")).toBeInTheDocument(); // previsão
    expect(linha.getByText("15/12/2026")).toBeInTheDocument(); // CASV
    expect(linha.getByText("Pendente")).toBeInTheDocument(); // o status continua Pendente
    expect(linha.queryByLabelText("orientação fornecida")).not.toBeInTheDocument();
  });

  it("depois que a orientação foi dada, marca a previsão com ✓", () => {
    render(<TabelaProcessos linhas={[obt({ orientacao: "Fornecidas" })]} tipo="OBT" />);
    expect(screen.getByLabelText("orientação fornecida")).toBeInTheDocument();
  });

  it("sem CASV não há previsão: travessão", () => {
    render(<TabelaProcessos linhas={[obt({ data_casv: null, previsao_orientacao: null })]} tipo="OBT" />);
    expect(screen.queryByText("01/12/2026")).not.toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });
});
