import {
  descreverAuditoria,
  gerarSenha,
  iniciais,
  SENHA_MINIMA,
  temSenha,
  validarSenha,
  validarUsuarioNovo,
  type RegistroAuditoria,
} from "@/lib/usuarios";

describe("senha", () => {
  it("mínimo igual ao da API e confirmação", () => {
    expect(validarSenha("curta")).toHaveProperty("senha");
    expect(validarSenha("a".repeat(SENHA_MINIMA))).toEqual({});
    expect(validarSenha("a".repeat(SENHA_MINIMA), "b".repeat(SENHA_MINIMA))).toHaveProperty("confirmacao");
  });

  it("gerada: 3 grupos de 4, sem caracteres que confundem, e passa no mínimo", () => {
    const senha = gerarSenha();
    expect(senha).toMatch(/^[A-Za-z2-9]{4}-[A-Za-z2-9]{4}-[A-Za-z2-9]{4}$/);
    expect(senha).not.toMatch(/[01OIl]/);
    expect(validarSenha(senha)).toEqual({});
  });

  it("usa o gerador recebido (determinístico no teste)", () => {
    const zeros = () => new Uint32Array(12);
    expect(gerarSenha(3, zeros)).toBe("AAAA-AAAA-AAAA");
  });
});

describe("usuário novo", () => {
  it("nome, e-mail e senha", () => {
    expect(Object.keys(validarUsuarioNovo({ nome: " ", email: "x@", senha: "123" })).sort()).toEqual([
      "email",
      "nome",
      "senha",
    ]);
    expect(validarUsuarioNovo({ nome: "Ana", email: "ana@concept.com", senha: "Kq7m-Xa3P-tR9w" })).toEqual(
      {},
    );
  });

  it("para quem não é admin a senha nem é pedida (entra com o Google)", () => {
    const sem = { nome: "Ana", email: "ana@concept.com", senha: "" };
    expect(validarUsuarioNovo(sem, false)).toEqual({});
    expect(Object.keys(validarUsuarioNovo(sem))).toEqual(["senha"]);
    expect(Object.keys(validarUsuarioNovo({ nome: "", email: "x", senha: "" }, false)).sort()).toEqual([
      "email",
      "nome",
    ]);
  });

  it("só o admin tem senha", () => {
    expect([temSenha("admin"), temSenha("atendente"), temSenha("leitor")]).toEqual([true, false, false]);
  });

  it("iniciais do crachá", () => {
    expect(iniciais("Ana Beatriz Moura")).toBe("AM");
    expect(iniciais("ana")).toBe("A");
    expect(iniciais("  ")).toBe("?");
  });
});

describe("auditoria", () => {
  const r = (campo: string, antes: string | null, depois: string | null): RegistroAuditoria => ({
    id: 1,
    usuario_id: 2,
    feito_por_id: 1,
    campo,
    valor_anterior: antes,
    valor_novo: depois,
    criado_em: "2026-11-07T15:00:00Z",
  });

  it("frases em português, sem nunca mostrar senha", () => {
    expect(descreverAuditoria(r("criado", null, "atendente"))).toBe("Usuário criado como Atendente");
    expect(descreverAuditoria(r("perfil", "leitor", "admin"))).toBe("Perfil: Leitor → Administrador");
    expect(descreverAuditoria(r("ativo", "True", "False"))).toBe("Acesso desativado");
    expect(descreverAuditoria(r("ativo", "False", "True"))).toBe("Acesso reativado");
    expect(descreverAuditoria(r("senha", null, "redefinida"))).toBe("Senha redefinida por um administrador");
    expect(descreverAuditoria(r("senha", null, "trocada pelo próprio usuário"))).toBe(
      "Trocou a própria senha",
    );
    expect(descreverAuditoria(r("senha", null, "removida (deixou de ser administrador)"))).toBe(
      "Senha removida: passa a entrar só com o Google",
    );
  });
});
