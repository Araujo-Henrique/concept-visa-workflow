import {
  corpoCliente,
  corpoEdicao,
  corpoProcessoNovo,
  formatarTelefone,
  linkWhatsapp,
  normalizarCodigo,
  PADRAO_DS160,
  validarCliente,
  validarProcesso,
  valoresDoProcesso,
  valoresIniciais,
} from "@/lib/formularios";

describe("telefone", () => {
  it("formata celular e fixo", () => {
    expect(formatarTelefone("41999990001")).toBe("(41) 99999-0001");
    expect(formatarTelefone("4133330001")).toBe("(41) 3333-0001");
    expect(formatarTelefone(null)).toBe("—");
  });

  it("monta o link do WhatsApp com o 55 do Brasil", () => {
    expect(linkWhatsapp("41999990001")).toBe("https://wa.me/5541999990001");
    expect(linkWhatsapp("123")).toBeNull();
  });
});

describe("cliente", () => {
  it("nome obrigatório, e-mail e telefone conferidos", () => {
    expect(validarCliente({ nome: " " })).toHaveProperty("nome");
    expect(validarCliente({ nome: "Ana", email: "ana@" })).toHaveProperty("email");
    expect(validarCliente({ nome: "Ana", telefone: "9999" })).toHaveProperty("telefone");
    expect(validarCliente({ nome: "Ana", email: "ana@x.com", telefone: "(41) 99999-0001" })).toEqual({});
  });

  it("corpo para a API: aparado, e-mail minúsculo, vazio vira null", () => {
    expect(corpoCliente({ nome: " Ana ", email: " Ana@X.com ", telefone: "", grupo: "" })).toEqual({
      nome: "Ana",
      email: "ana@x.com",
      telefone: null,
      grupo: null,
    });
  });
});

describe("regras do processo", () => {
  it("OBT: agendada pede data; data pede consulado", () => {
    const v = { ...valoresIniciais("OBT"), orientacao: "Agendada", data_casv: "2026-12-01" };
    expect(Object.keys(validarProcesso("OBT", v)).sort()).toEqual(["consulado", "orientacao_data"]);
  });

  it("REN: CASV pede consulado", () => {
    expect(validarProcesso("REN", { ...valoresIniciais("REN"), data_casv: "2026-12-01" })).toHaveProperty(
      "consulado",
    );
  });

  it("passaporte: prazo não vem antes da PF", () => {
    expect(validarProcesso("PASS", { data_pf: "2026-12-10", prazo_pf: "2026-12-01" })).toHaveProperty(
      "prazo_pf",
    );
  });

  it("editando o histórico, só cobra o consulado se mexer nele ou nas datas (como a API)", () => {
    const antigo = { ...valoresIniciais("OBT"), data_casv: "2024-03-03" };
    expect(validarProcesso("OBT", antigo, new Set(["observacao"]))).toEqual({});
    expect(validarProcesso("OBT", antigo, new Set(["data_casv"]))).toHaveProperty("consulado");
  });
});

describe("corpo do processo", () => {
  it("novo: datas vazias viram null, orientador vira número, extras sem vazios", () => {
    const v = { ...valoresIniciais("OBT"), consulado: "SP", data_casv: "2026-12-01", orientacao_por_id: "3" };
    const corpo = corpoProcessoNovo("OBT", 7, "Cadastro", v, ["Laura", " ", "Miguel "]);
    expect(corpo).toMatchObject({
      cliente_id: 7,
      situacao: "Cadastro",
      solicitantes_extras: ["Laura", "Miguel"],
      consulado: "SP",
      data_casv: "2026-12-01",
      data_entrevista: null,
      orientacao_por_id: 3,
      status_rascunho: "Pendente",
    });
  });

  it("edição: só os campos que mudaram", () => {
    const antes = valoresDoProcesso("REN", { consulado: "SP", data_casv: "2026-12-01", docs: "Pendente" });
    const depois = { ...antes, docs: "Entregue", data_casv: "" };
    expect(corpoEdicao("REN", antes, depois)).toEqual({ docs: "Entregue", data_casv: null });
  });

  it("lê do processo gravado: data com hora vira só a data, nulo vira vazio", () => {
    const v = valoresDoProcesso("PASS", { data_pf: "2026-12-01T00:00:00", prazo_pf: null, observacao: null });
    expect(v).toEqual({ data_pf: "2026-12-01", prazo_pf: "", observacao: "" });
  });
});

describe("DS-160", () => {
  it("normaliza e confere o formato AA00 + 6", () => {
    expect(normalizarCodigo(" aa00 abc123 ")).toBe("AA00ABC123");
    expect(PADRAO_DS160.test("AA00ABC123")).toBe(true);
    expect(PADRAO_DS160.test("AA00ABC12")).toBe(false);
  });
});
