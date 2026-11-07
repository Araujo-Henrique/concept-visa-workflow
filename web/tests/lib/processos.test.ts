import {
  dataEHora,
  datasPrincipais,
  formatarData,
  formatarDataCurta,
  haFiltros,
  inclinacaoDoCarimbo,
  lerFiltros,
  linhaDeMaquina,
  paramsDoPainel,
  rotuloResultado,
  tomDaSituacao,
  tomDoResultado,
  urlDosFiltros,
} from "@/lib/processos";
import type { LinhaPainel } from "@/lib/tipos";

describe("datas", () => {
  it("lê a data como texto: 01/12 continua 01/12 no Brasil (sem virar 30/11 pelo fuso)", () => {
    expect(formatarData("2026-12-01")).toBe("01/12/2026");
    expect(formatarDataCurta("2026-12-01")).toBe("01 dez");
  });

  it("data e hora de um evento no horário de Brasília (sem a vírgula do formato pt-BR)", () => {
    expect(dataEHora("2026-11-06T02:30:00+00:00")).toEqual(["05/11/2026", "23:30"]);
  });

  it("data vazia vira travessão", () => {
    expect(formatarData(null)).toBe("—");
    expect(formatarDataCurta(undefined)).toBe("—");
  });
});

describe("tons de situação e resultado", () => {
  it.each([
    ["Boleto", "pagamento"],
    ["Pix", "pagamento"],
    ["Limbo", "parado"],
    ["Concluido", "concluido"],
    ["Processando", "andamento"],
    ["Situação nova qualquer", "andamento"],
  ])("%s -> %s", (situacao, tom) => {
    expect(tomDaSituacao(situacao)).toBe(tom);
  });

  it("resultado pendente aparece como 'Aguardando' (não confunde com a situação Processando)", () => {
    expect(rotuloResultado("Processando")).toBe("Aguardando");
    expect(rotuloResultado("Aprovado")).toBe("Aprovado");
  });

  it("resultado", () => {
    expect(tomDoResultado("Aprovado")).toBe("aprovado");
    expect(tomDoResultado("Negado")).toBe("negado");
    expect(tomDoResultado("Parcial")).toBe("parcial");
    expect(tomDoResultado("Processando")).toBe("andamento");
  });
});

describe("datas principais por tipo", () => {
  const base = { processo_id: 1, situacao: "x", cliente_id: 1, cliente: "A" } as unknown as LinhaPainel;
  it("cada tipo mostra as datas que tem", () => {
    const obt = { ...base, tipo: "OBT", data_casv: "2026-12-01", data_entrevista: null } as LinhaPainel;
    expect(datasPrincipais(obt).map((d) => d.rotulo)).toEqual(["CASV", "Entrevista"]);
    expect(datasPrincipais({ ...base, tipo: "REN" } as LinhaPainel).map((d) => d.rotulo)).toEqual([
      "CASV",
      "Despacho",
    ]);
    expect(datasPrincipais({ ...base, tipo: "PASS" } as LinhaPainel).map((d) => d.rotulo)).toEqual([
      "PF",
      "Prazo",
    ]);
  });
});

describe("filtros da URL", () => {
  it("padrões: OBT, tabela, página 1", () => {
    expect(lerFiltros({})).toMatchObject({ tipo: "OBT", visao: "tabela", pagina: 1 });
  });

  it("descarta o que é inválido (URL editada à mão não quebra a tela)", () => {
    const f = lerFiltros({ tipo: "XYZ", pagina: "-3", visao: "outra", data: "nascimento", de: "2026-01-01" });
    expect(f).toMatchObject({ tipo: "OBT", pagina: 1, visao: "tabela", data: undefined, de: undefined });
    expect(lerFiltros({ de: "ontem", data: "casv" }).de).toBeUndefined();
  });

  it("data só vale se existir no tipo; passaporte não tem consulado", () => {
    expect(lerFiltros({ tipo: "PASS", data: "casv", de: "2026-01-01" }).data).toBeUndefined();
    expect(lerFiltros({ tipo: "PASS", consulado: "SP" }).consulado).toBeUndefined();
    expect(lerFiltros({ tipo: "REN", data: "despacho", de: "2026-01-01" })).toMatchObject({
      data: "despacho",
      de: "2026-01-01",
    });
  });

  it("filtro de despacho só no REN e só com os valores conhecidos", () => {
    expect(lerFiltros({ tipo: "REN", despacho: "pendente" }).despacho).toBe("pendente");
    expect(lerFiltros({ tipo: "REN", despacho: "talvez" }).despacho).toBeUndefined();
    expect(lerFiltros({ tipo: "OBT", despacho: "feito" }).despacho).toBeUndefined();
    expect(paramsDoPainel(lerFiltros({ tipo: "REN", despacho: "feito" }))).toMatchObject({
      despacho: "feito",
    });
  });

  it("vira os parâmetros da API, com paginação", () => {
    const f = lerFiltros({ tipo: "OBT", cliente: "souza", resultado: "Negado", pagina: "3" });
    expect(paramsDoPainel(f)).toMatchObject({
      tipo: "OBT",
      cliente: "souza",
      resultado_geral: "Negado",
      limit: 50,
      offset: 100,
    });
  });

  it("a data só segue para a API quando há período", () => {
    expect(paramsDoPainel(lerFiltros({ data: "casv" })).data).toBeUndefined();
    expect(paramsDoPainel(lerFiltros({ data: "casv", ate: "2026-12-31" })).data).toBe("casv");
  });

  it("monta a URL sem os valores padrão", () => {
    expect(urlDosFiltros({ tipo: "OBT", visao: "tabela", pagina: 1 })).toBe("/processos");
    expect(urlDosFiltros({ tipo: "REN", situacao: "Cadastro", pagina: 2 })).toBe(
      "/processos?tipo=REN&situacao=Cadastro&pagina=2",
    );
  });

  it("sabe se há filtro ligado", () => {
    expect(haFiltros(lerFiltros({ tipo: "REN" }))).toBe(false);
    expect(haFiltros(lerFiltros({ cliente: "ana" }))).toBe(true);
  });
});

describe("passaporte", () => {
  it("linha de máquina: só A-Z, dígitos e <, com 44 caracteres", () => {
    const [l1, l2] = linhaDeMaquina("OBT", 1234, "José da Silva Conceição");
    expect(l1).toMatch(/^P<CVBCONCEICAO<<JOSE<DA<SILVA<+$/);
    expect(l2.startsWith("OBT000001234<BRA")).toBe(true);
    expect([l1.length, l2.length]).toEqual([44, 44]);
  });

  it("carimbo tem sempre a mesma inclinação, entre -7° e 7°", () => {
    expect(inclinacaoDoCarimbo(42)).toBe(inclinacaoDoCarimbo(42));
    for (let id = 1; id < 200; id++) expect(Math.abs(inclinacaoDoCarimbo(id))).toBeLessThanOrEqual(7);
  });
});
