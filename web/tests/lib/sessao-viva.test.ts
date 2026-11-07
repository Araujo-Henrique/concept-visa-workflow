import { AVISO, contagem, decidir, lerExpiracao, RENOVAR_A_CADA, urlDoLogin } from "@/lib/sessao-viva";

// Sessão deslizante: renova enquanto há uso, avisa quando a pessoa está parada, sai quando vence.
const MIN = 60_000;
const base = { agora: 100 * MIN, ultimaAtividade: 0, ultimaRenovacao: 0, noLimite: false };

describe("decidir", () => {
  it("vencida: vai para o login, mesmo com uso", () => {
    expect(decidir({ ...base, expiraEm: base.agora, ultimaAtividade: base.agora })).toBe("sair");
  });

  it("parada e longe de vencer: não faz nada", () => {
    expect(decidir({ ...base, expiraEm: base.agora + 20 * MIN })).toBe("nada");
  });

  it("em uso: renova, mas no máximo a cada 5 minutos", () => {
    const usando = { ...base, expiraEm: base.agora + 20 * MIN, ultimaAtividade: base.agora - 1000 };
    expect(decidir({ ...usando, ultimaRenovacao: base.agora - RENOVAR_A_CADA })).toBe("renovar");
    expect(decidir({ ...usando, ultimaRenovacao: base.agora - 2 * MIN })).toBe("nada");
  });

  it("uso de antes da última renovação não conta", () => {
    expect(
      decidir({
        ...base,
        expiraEm: base.agora + 20 * MIN,
        ultimaAtividade: base.agora - 10 * MIN,
        ultimaRenovacao: base.agora - 9 * MIN,
      }),
    ).toBe("nada");
  });

  it("parada e quase vencendo: avisa", () => {
    expect(decidir({ ...base, expiraEm: base.agora + AVISO })).toBe("avisar");
  });

  it("quase vencendo e voltou a usar: renova na hora, sem esperar os 5 minutos", () => {
    expect(
      decidir({
        ...base,
        expiraEm: base.agora + MIN,
        ultimaAtividade: base.agora - 1000,
        ultimaRenovacao: base.agora - 30_000,
      }),
    ).toBe("renovar");
  });

  it("no teto da sessão: não tenta renovar, só avisa", () => {
    expect(
      decidir({ ...base, expiraEm: base.agora + MIN, ultimaAtividade: base.agora, noLimite: true }),
    ).toBe("avisar");
  });

  it("sessão antiga sem o cookie de validade: renova no primeiro uso", () => {
    expect(decidir({ ...base, expiraEm: null, ultimaAtividade: 1, ultimaRenovacao: 0 })).toBe("renovar");
    expect(decidir({ ...base, expiraEm: null })).toBe("nada");
  });
});

describe("apoio", () => {
  it("lê a validade do document.cookie", () => {
    expect(lerExpiracao("cv_tema=escuro; cv_expira=1767225600000; outro=1")).toBe(1767225600000);
    expect(lerExpiracao("cv_tema=escuro")).toBeNull();
    expect(lerExpiracao("cv_expira=lixo")).toBeNull();
  });

  it("contagem regressiva m:ss", () => {
    expect(contagem(65_000)).toBe("1:05");
    expect(contagem(8_200)).toBe("0:09");
    expect(contagem(-5)).toBe("0:00");
  });

  it("login com aviso de sessão vencida e o caminho de volta", () => {
    expect(urlDoLogin("/processos/12?aba=dados")).toBe("/login?expirou=1&de=%2Fprocessos%2F12%3Faba%3Ddados");
    expect(urlDoLogin("/")).toBe("/login?expirou=1");
  });
});
