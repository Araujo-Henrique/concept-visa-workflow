import { ativo } from "@/components/shell/navegacao";
import { emAndamento, rotuloSituacao, saudacao, situacoesAbertas } from "@/lib/formatos";
import { montarCaminho } from "@/lib/api";

describe("saudacao (horário de Brasília)", () => {
  it.each([
    ["2026-11-05T10:00:00Z", "Bom dia"], // 07h em Brasília
    ["2026-11-05T17:00:00Z", "Boa tarde"], // 14h
    ["2026-11-05T23:30:00Z", "Boa noite"], // 20h30
    ["2026-11-05T05:00:00Z", "Boa noite"], // 02h
  ])("%s -> %s", (iso, esperado) => {
    expect(saudacao(new Date(iso))).toBe(esperado);
  });
});

describe("resumo por situação", () => {
  const porSituacao = { Concluido: 3300, Processando: 74, Pago: 31, Cadastro: 6 };

  it("em andamento é tudo que não está concluído", () => {
    expect(emAndamento(porSituacao)).toBe(111);
    expect(emAndamento({})).toBe(0);
  });

  it("lista as situações abertas da mais cheia para a mais vazia", () => {
    expect(situacoesAbertas(porSituacao)).toEqual([
      ["Processando", 74],
      ["Pago", 31],
      ["Cadastro", 6],
    ]);
  });

  it("mostra os nomes com acento", () => {
    expect(rotuloSituacao("Concluido")).toBe("Concluído");
    expect(rotuloSituacao("Pix")).toBe("Pix");
  });
});

describe("menu", () => {
  it("Início só fica ativo na raiz; os demais também nas subpáginas", () => {
    expect(ativo("/", "/")).toBe(true);
    expect(ativo("/", "/processos")).toBe(false);
    expect(ativo("/processos", "/processos/12")).toBe(true);
    expect(ativo("/processos", "/processosx")).toBe(false);
  });
});

describe("montarCaminho", () => {
  it("monta a query só com valores preenchidos", () => {
    expect(montarCaminho("/painel", { tipo: "OBT", situacao: "", cliente: undefined, limit: 50 })).toBe(
      "/painel?tipo=OBT&limit=50",
    );
    expect(montarCaminho("/painel")).toBe("/painel");
  });
});
