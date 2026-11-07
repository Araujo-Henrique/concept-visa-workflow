/**
 * @jest-environment jsdom
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Calendario } from "@/components/agenda/calendario";
import { gradeDoMes } from "@/lib/agenda";
import type { AgendaItem } from "@/lib/tipos";

const item = (data: string, evento: AgendaItem["evento"], id: number, cliente: string): AgendaItem => ({
  data,
  evento,
  processo_id: id,
  tipo: "OBT",
  cliente,
  situacao: "Cadastro",
  consulado: "SP",
});

const itens = [
  item("2026-11-07", "casv", 1, "Ana Lima"),
  item("2026-11-07", "entrevista", 2, "Bruno Reis"),
  item("2026-11-12", "orientacao", 3, "Carla Dias"),
];

function montar() {
  render(<Calendario mes="2026-11" hoje="2026-11-07" dias={gradeDoMes("2026-11")} itens={itens} />);
  return within(screen.getByRole("complementary", { name: "Compromissos do dia" }));
}

describe("Calendário da agenda", () => {
  it("abre em hoje, com os compromissos do dia e o link do processo", () => {
    const painel = montar();
    expect(painel.getByText("Hoje")).toBeInTheDocument();
    expect(painel.getByRole("link", { name: /Ana Lima/ })).toHaveAttribute("href", "/processos/1");
    expect(painel.getByRole("link", { name: /Bruno Reis/ })).toBeInTheDocument();
  });

  it("clicar em outro dia mostra os compromissos dele", async () => {
    const painel = montar();
    await userEvent.click(screen.getByRole("button", { name: /12 de novembro: 1 compromisso/ }));
    expect(await painel.findByRole("link", { name: /Carla Dias/ })).toBeInTheDocument();
  });

  it("as setas do teclado andam pelos dias", async () => {
    const painel = montar();
    screen.getByRole("button", { name: /^sábado, 7 de novembro/ }).focus();
    await userEvent.keyboard("{ArrowRight}{ArrowRight}{ArrowRight}{ArrowRight}{ArrowRight}"); // 7 -> 12
    expect(screen.getByRole("button", { name: /^quinta-feira, 12 de novembro/ })).toHaveFocus();
    expect(await painel.findByRole("link", { name: /Carla Dias/ })).toBeInTheDocument();
  });

  it("desligar um tipo esconde esses compromissos", async () => {
    const painel = montar();
    await userEvent.click(screen.getByRole("button", { name: /Entrevista/, pressed: true }));
    expect(painel.queryByRole("link", { name: /Bruno Reis/ })).not.toBeInTheDocument();
    expect(painel.getByRole("link", { name: /Ana Lima/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /7 de novembro: 1 compromisso/ })).toBeInTheDocument();
  });
});
