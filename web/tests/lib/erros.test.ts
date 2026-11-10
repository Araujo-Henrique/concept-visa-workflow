import { destinoSeguro, mensagemDeErro } from "@/lib/erros";

describe("mensagemDeErro", () => {
  it("usa o texto da API quando é uma regra de negócio", () => {
    expect(mensagemDeErro(409, "Sair de Concluido exige motivo")).toBe("Sair de Concluido exige motivo");
  });

  it("resume os campos inválidos do Pydantic (422)", () => {
    const detail = [
      { loc: ["body", "email"], msg: "x" },
      { loc: ["body", "senha"], msg: "y" },
      { loc: ["body", "email"], msg: "z" },
    ];
    expect(mensagemDeErro(422, detail)).toBe("Confira os campos: email, senha.");
    expect(mensagemDeErro(422, [{ loc: ["body", "nome"] }])).toBe("Confira o campo: nome.");
  });

  it("cai numa mensagem amigável por status quando não há detalhe", () => {
    expect(mensagemDeErro(403, null)).toBe("Seu perfil não permite esta ação.");
    expect(mensagemDeErro(503, undefined)).toMatch(/indisponível/);
    expect(mensagemDeErro(500, null)).toBe("A API teve um erro interno ao buscar esses dados.");
    expect(mensagemDeErro(418, "")).toBe("Algo deu errado. Tente de novo.");
  });
});

describe("destinoSeguro (para onde ir depois do login)", () => {
  it.each([
    ["/processos?tipo=OBT", "/processos?tipo=OBT"],
    ["/clientes/12", "/clientes/12"],
    [null, "/"],
    ["", "/"],
    ["https://outro-site.com", "/"], // nunca sai do sistema
    ["//outro-site.com", "/"],
    ["/\\outro-site.com", "/"],
    ["/login?de=/x", "/"], // não volta para o próprio login
    ["/\t/outro-site.com", "/"], // o navegador tira o tab e vira //outro-site.com
    ["/\n/outro-site.com", "/"],
    ["/\r/outro-site.com", "/"],
    ["/ok\u0000", "/"],
    ["/a\\b", "/"],
  ])("%s -> %s", (entrada, esperado) => {
    expect(destinoSeguro(entrada)).toBe(esperado);
  });
});
