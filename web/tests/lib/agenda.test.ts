import {
  agruparPorDia,
  contarPorEvento,
  diasEntre,
  gradeDoMes,
  hojeEmSP,
  lerMes,
  mesVizinho,
  nomeDoMes,
  rotuloDoDia,
  somarDias,
  tituloDoDia,
  urlDaAgenda,
} from "@/lib/agenda";
import type { AgendaItem } from "@/lib/tipos";

describe("dias", () => {
  it("hoje é o dia de Brasília, mesmo quando em UTC já virou", () => {
    // 01h UTC de 08/11 = 22h de 07/11 em São Paulo
    expect(hojeEmSP(new Date("2026-11-08T01:00:00Z"))).toBe("2026-11-07");
  });

  it("soma dias atravessando mês e ano", () => {
    expect(somarDias("2026-12-30", 3)).toBe("2027-01-02");
    expect(somarDias("2026-03-01", -1)).toBe("2026-02-28");
    expect(diasEntre("2026-11-07", "2026-11-14")).toBe(7);
  });
});

describe("mês", () => {
  it("lê o mês da URL e cai no mês de hoje se for inválido", () => {
    expect(lerMes("2027-01", "2026-11-07")).toBe("2027-01");
    expect(lerMes("2027-13", "2026-11-07")).toBe("2026-11");
    expect(lerMes(undefined, "2026-11-07")).toBe("2026-11");
    expect(lerMes(["2026-05", "x"], "2026-11-07")).toBe("2026-05");
  });

  it("anda entre meses e nomeia em português", () => {
    expect(mesVizinho("2026-12", 1)).toBe("2027-01");
    expect(mesVizinho("2026-01", -1)).toBe("2025-12");
    expect(nomeDoMes("2026-03")).toBe("março de 2026");
  });

  it("grade de segunda a domingo, com semanas inteiras", () => {
    const nov = gradeDoMes("2026-11"); // 01/11/2026 é domingo
    expect(nov[0]).toBe("2026-10-26");
    expect(nov[6]).toBe("2026-11-01");
    expect(nov.length % 7).toBe(0);
    expect(nov.at(-1)! >= "2026-11-30").toBe(true);

    const fev = gradeDoMes("2027-02"); // 01/02/2027 é segunda: começa no próprio dia 1
    expect(fev[0]).toBe("2027-02-01");
    expect(fev).toHaveLength(28);
  });
});

describe("compromissos", () => {
  const item = (data: string, evento: AgendaItem["evento"], id = 1): AgendaItem => ({
    data,
    evento,
    processo_id: id,
    tipo: "OBT",
    cliente: "Cliente",
    situacao: "Cadastro",
    consulado: "SP",
  });

  it("agrupa por dia e conta por tipo", () => {
    const itens = [
      item("2026-11-10", "casv"),
      item("2026-11-10", "casv", 2),
      item("2026-11-11", "entrevista"),
    ];
    expect(agruparPorDia(itens).get("2026-11-10")).toHaveLength(2);
    expect(contarPorEvento(itens)).toEqual({ casv: 2, entrevista: 1 });
  });

  it("rótulos do dia relativos a hoje", () => {
    expect(rotuloDoDia("2026-11-07", "2026-11-07")).toBe("Hoje");
    expect(rotuloDoDia("2026-11-08", "2026-11-07")).toBe("Amanhã");
    expect(rotuloDoDia("2026-11-06", "2026-11-07")).toBe("Ontem");
    expect(rotuloDoDia("2026-11-11", "2026-11-07")).toBe("qua, 11 nov");
    expect(tituloDoDia("2026-11-11")).toBe("quarta-feira, 11 de novembro");
  });

  it("link da agenda sem o mês atual", () => {
    expect(urlDaAgenda("2026-11", "2026-11-07")).toBe("/agenda");
    expect(urlDaAgenda("2026-12", "2026-11-07")).toBe("/agenda?mes=2026-12");
  });
});
