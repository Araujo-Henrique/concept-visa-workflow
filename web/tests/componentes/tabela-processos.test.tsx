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
  ds160_status: null,
  ds160_fechados: 0,
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

  it("orientação agendada mostra a data marcada (ela conta na ordem da tabela)", () => {
    render(
      <TabelaProcessos
        linhas={[obt({ orientacao: "Agendada", orientacao_data: "2026-11-24" })]}
        tipo="OBT"
      />,
    );
    const linha = within(screen.getByRole("row", { name: /Joana Prado Lins/ }));
    expect(linha.getByText("Agendada")).toBeInTheDocument();
    expect(linha.getByText("24/11/2026")).toBeInTheDocument();
  });

  it("orientação que não está agendada não mostra data embaixo do selo", () => {
    render(
      <TabelaProcessos linhas={[obt({ orientacao: "Opt A", orientacao_data: "2026-11-24" })]} tipo="OBT" />,
    );
    expect(screen.queryByText("24/11/2026")).not.toBeInTheDocument();
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

describe("Tabela de processos: coluna DS-160", () => {
  it("mostra o status do formulário ao lado da situação, para ver de relance", () => {
    render(
      <TabelaProcessos
        linhas={[obt({ ds160_status: "Aberto", ds160_fechados: 0, n_formularios: 1 })]}
        tipo="OBT"
      />,
    );
    expect(screen.getByRole("columnheader", { name: "DS-160" })).toBeInTheDocument();
    const linha = within(screen.getByRole("row", { name: /Joana Prado Lins/ }));
    expect(linha.getByText("Aberto")).toBeInTheDocument();
    expect(linha.queryByText(/fechados/)).not.toBeInTheDocument(); // um formulário só: sem contagem
  });

  it("com vários formulários mostra o menos avançado e quantos já fecharam", () => {
    render(
      <TabelaProcessos
        linhas={[obt({ ds160_status: "Aberto", ds160_fechados: 2, n_formularios: 3, n_solicitantes: 3 })]}
        tipo="OBT"
      />,
    );
    expect(screen.getByText("Aberto")).toBeInTheDocument();
    expect(screen.getByText("2/3 fechados")).toBeInTheDocument();
  });

  it("avisa quando há pessoas sem DS-160 cadastrado", () => {
    render(
      <TabelaProcessos
        linhas={[obt({ ds160_status: "Fechado", ds160_fechados: 1, n_formularios: 1, n_solicitantes: 3 })]}
        tipo="OBT"
      />,
    );
    expect(screen.getByText("Fechado")).toBeInTheDocument();
    expect(screen.getByText("2 sem DS-160")).toBeInTheDocument();
  });

  it("sem formulário: travessão com a explicação", () => {
    render(<TabelaProcessos linhas={[obt()]} tipo="OBT" />);
    expect(screen.getByTitle("Nenhum DS-160 cadastrado")).toHaveTextContent("—");
  });

  it("passaporte não tem a coluna de DS-160", () => {
    const pass = {
      ...obt(),
      tipo: "PASS",
      data_pf: null,
      prazo_pf: null,
    } as unknown as Parameters<typeof TabelaProcessos>[0]["linhas"][number];
    render(<TabelaProcessos linhas={[pass]} tipo="PASS" />);
    expect(screen.queryByRole("columnheader", { name: "DS-160" })).not.toBeInTheDocument();
  });
});
