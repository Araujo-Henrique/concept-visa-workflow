/** @jest-environment node */
import { NextRequest } from "next/server";

import { proxy } from "@/proxy";

// Sem cookie, a página vai para o login. Mas uma Server Action não pode receber o HTML do login de volta
// (a tela quebrava com "An unexpected response was received from the server"): ela passa direto e o
// lib/api.ts responde com um redirect que o Next entende.
const pedido = (caminho: string, init: { method?: string; headers?: Record<string, string> } = {}) =>
  new NextRequest(new URL(caminho, "http://localhost:3000"), init);

describe("proxy", () => {
  it("sem sessão, a página vai para o login guardando o destino", () => {
    const r = proxy(pedido("/processos/novo"));
    expect(r.status).toBe(307);
    const destino = new URL(r.headers.get("location")!);
    expect(destino.pathname).toBe("/login");
    expect(destino.searchParams.get("de")).toBe("/processos/novo");
  });

  it("sem sessão, a Server Action passa (quem responde é o lib/api.ts)", () => {
    const r = proxy(pedido("/processos/novo", { method: "POST", headers: { "next-action": "abc123" } }));
    expect(r.headers.get("location")).toBeNull();
    expect(r.headers.get("x-middleware-next")).toBe("1");
  });

  it("POST sem o cabeçalho de Server Action continua indo para o login", () => {
    expect(proxy(pedido("/processos/novo", { method: "POST" })).status).toBe(307);
  });

  it("com sessão, segue", () => {
    const r = proxy(pedido("/", { headers: { cookie: "cv_sessao=qualquer" } }));
    expect(r.headers.get("x-middleware-next")).toBe("1");
  });
});
