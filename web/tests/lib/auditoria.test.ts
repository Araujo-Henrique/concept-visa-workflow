import {
  type Alteracao,
  agruparAlteracoes,
  autorDaAlteracao,
  descreverAlteracao,
  formatarValor,
  rotuloDoCampo,
} from "@/lib/auditoria";

// Auditoria na tela: linhas cruas da API (colunas do banco, JSON) viram frases para quem administra.
let proximoId = 1;
const linha = (parcial: Partial<Alteracao>): Alteracao => ({
  id: proximoId++,
  tabela: "clientes",
  registro_id: 7,
  processo_id: null,
  cliente_id: 7,
  acao: "editou",
  antes: null,
  depois: null,
  usuario_id: 1,
  usuario_nome: "Henrique Araujo",
  requisicao: "ab12cd34ef56",
  origem: "api",
  transacao: 100,
  criado_em: "2026-11-09T17:30:00Z",
  ...parcial,
});

describe("formatarValor e rotuloDoCampo", () => {
  it("mostra datas, telefones, sim/não, ids e vazio do jeito da tela", () => {
    expect(formatarValor("data_casv", "2026-12-01")).toBe("01/12/2026");
    expect(formatarValor("telefone", "41999998888")).toBe("(41) 99999-8888");
    expect(formatarValor("titular", true)).toBe("sim");
    expect(formatarValor("titular", false)).toBe("não");
    expect(formatarValor("processo_anterior_id", 12)).toBe("#12");
    expect(formatarValor("orientacao_por_id", 3)).toBe("usuário #3");
    expect(formatarValor("grupo", null)).toBe("—");
    expect(formatarValor("grupo", "")).toBe("—");
  });

  it("dá nome de gente às colunas; coluna desconhecida vira texto legível", () => {
    expect(rotuloDoCampo("data_casv")).toBe("Data do CASV");
    expect(rotuloDoCampo("campo_novo_qualquer")).toBe("Campo novo qualquer");
  });
});

describe("autorDaAlteracao", () => {
  it("o nome de quem fez; sem usuário, a origem", () => {
    expect(autorDaAlteracao({ usuario_id: 1, usuario_nome: "Ana", origem: "api" })).toBe("Ana");
    expect(autorDaAlteracao({ usuario_id: 9, usuario_nome: null, origem: "api" })).toBe("usuário #9");
    expect(autorDaAlteracao({ usuario_id: null, usuario_nome: null, origem: "banco" })).toBe(
      "alteração direta no banco",
    );
    expect(autorDaAlteracao({ usuario_id: null, usuario_nome: null, origem: "importacao" })).toBe(
      "importação do sistema antigo",
    );
  });
});

describe("descreverAlteracao", () => {
  it("edição: cada campo que mudou, com antes e depois, sem colunas técnicas", () => {
    const d = descreverAlteracao(
      linha({ antes: { grupo: null, atualizado_em: "x" }, depois: { grupo: "Família", atualizado_em: "y" } }),
    );
    expect(d).toEqual({
      id: expect.any(Number),
      titulo: "Dados do cliente editados",
      campos: [{ rotulo: "Grupo", antes: "—", depois: "Família" }],
    });
  });

  it("edição que só mexeu em coluna técnica não aparece", () => {
    expect(descreverAlteracao(linha({ antes: { tipo: "OBT" }, depois: { tipo: "REN" } }))).toBeNull();
  });

  it("remoção mostra os dados que existiam (é daqui que se recupera um cadastro apagado)", () => {
    const d = descreverAlteracao(
      linha({
        acao: "apagou",
        antes: { id: 7, nome: "Ana Souza", telefone: "41999998888", email: null, grupo: "" },
      }),
    );
    expect(d?.titulo).toBe("Cliente apagado: Ana Souza");
    expect(d?.campos).toEqual([
      { rotulo: "Nome", antes: "Ana Souza", depois: null },
      { rotulo: "Telefone", antes: "(41) 99999-8888", depois: null },
    ]);
  });

  it("títulos por tipo de registro", () => {
    const t = (p: Partial<Alteracao>) => descreverAlteracao(linha(p))?.titulo;
    expect(t({ acao: "criou", depois: { nome: "Ana" } })).toBe("Cliente cadastrado: Ana");
    expect(
      t({
        tabela: "processos",
        registro_id: 12,
        acao: "criou",
        depois: { tipo: "OBT", situacao: "Processando" },
      }),
    ).toBe("Processo OBT #12 aberto em Processando");
    expect(t({ tabela: "processos", antes: { situacao: "A" }, depois: { situacao: "B" } })).toBe(
      "Situação alterada",
    );
    expect(t({ tabela: "solicitantes", acao: "criou", depois: { nome: "Bia", titular: true } })).toBe(
      "Pessoa incluída: Bia (titular)",
    );
    expect(t({ tabela: "solicitantes", acao: "apagou", antes: { nome: "Bia", titular: false } })).toBe(
      "Pessoa removida: Bia",
    );
    expect(t({ tabela: "formularios_ds160", acao: "criou", depois: { codigo: "AA00ABC123" } })).toBe(
      "DS-160 AA00ABC123 cadastrado",
    );
  });

  it("a parte de detalhe de um processo criado ou apagado não repete a linha do processo", () => {
    expect(
      descreverAlteracao(linha({ tabela: "processo_obt", acao: "criou", depois: { consulado: "SP" } })),
    ).toBeNull();
    expect(
      descreverAlteracao(linha({ tabela: "processo_ren", acao: "apagou", antes: { docs: "X" } })),
    ).toBeNull();
    // mas a edição do detalhe aparece
    const editado = descreverAlteracao(
      linha({
        tabela: "processo_obt",
        registro_id: 5,
        antes: { consulado: null },
        depois: { consulado: "SP" },
      }),
    );
    expect(editado?.campos).toEqual([{ rotulo: "Consulado", antes: "—", depois: "SP" }]);
  });
});

describe("agruparAlteracoes", () => {
  it("junta a mesma transação num bloco, na ordem em que aconteceu; blocos do mais novo ao mais antigo", () => {
    // a API manda da mais nova para a mais antiga
    const lista = [
      linha({ transacao: 200, tabela: "clientes", acao: "apagou", antes: { nome: "Ana" } }),
      linha({ transacao: 200, tabela: "processo_obt", acao: "apagou", antes: { consulado: "SP" } }),
      linha({ transacao: 200, tabela: "processos", registro_id: 3, acao: "apagou", antes: { tipo: "OBT" } }),
      linha({
        transacao: 100,
        acao: "criou",
        depois: { nome: "Ana" },
        usuario_nome: null,
        usuario_id: null,
        origem: "seed",
      }),
    ];
    const grupos = agruparAlteracoes(lista);
    expect(grupos.map((g) => g.transacao)).toEqual([200, 100]);
    expect(grupos[0]!.itens.map((i) => i.titulo)).toEqual([
      "Processo OBT #3 apagado",
      "Cliente apagado: Ana",
    ]);
    expect(grupos[1]!.autor).toBe("dados de demonstração");
  });

  it("bloco só com linhas que não aparecem some", () => {
    expect(agruparAlteracoes([linha({ tabela: "processo_obt", acao: "criou", depois: {} })])).toEqual([]);
  });
});
