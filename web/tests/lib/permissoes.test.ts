import { pode } from "@/lib/permissoes";

describe("pode (espelho de app/permissoes.py)", () => {
  it("leitor só consulta", () => {
    expect(pode("leitor", "ler")).toBe(true);
    expect(pode("leitor", "escrever")).toBe(false);
  });

  it("atendente consulta e escreve, mas não apaga nem administra", () => {
    expect(pode("atendente", "escrever")).toBe(true);
    expect(pode("atendente", "apagar")).toBe(false);
    expect(pode("atendente", "administrar")).toBe(false);
  });

  it("admin pode tudo", () => {
    expect(["ler", "escrever", "apagar", "administrar"].every((a) => pode("admin", a as never))).toBe(true);
  });

  it("perfil desconhecido ou vazio não pode nada (nega por padrão)", () => {
    expect(pode("chefe", "ler")).toBe(false);
    expect(pode(undefined, "ler")).toBe(false);
    expect(pode("constructor", "ler")).toBe(false); // nem chaves herdadas de Object
  });
});
