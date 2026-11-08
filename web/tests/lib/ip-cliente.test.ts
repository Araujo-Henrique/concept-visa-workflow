import { ipDoEncaminhamento } from "@/lib/ip-cliente";

jest.mock("next/headers", () => ({ headers: async () => new Headers() }));

describe("ipDoEncaminhamento", () => {
  it("vale o último da lista: é o que o intermediário (ngrok, nginx) viu", () => {
    expect(ipDoEncaminhamento("1.1.1.1, 203.0.113.7")).toBe("203.0.113.7");
    expect(ipDoEncaminhamento("203.0.113.7")).toBe("203.0.113.7");
    expect(ipDoEncaminhamento("::1")).toBe("::1");
  });

  it("sem cabeçalho (ou vazio): não inventa IP", () => {
    expect(ipDoEncaminhamento(null)).toBeNull();
    expect(ipDoEncaminhamento(undefined)).toBeNull();
    expect(ipDoEncaminhamento(" , ")).toBeNull();
  });

  it("corta valores absurdos", () => {
    expect(ipDoEncaminhamento("x".repeat(500))).toHaveLength(64);
  });
});
