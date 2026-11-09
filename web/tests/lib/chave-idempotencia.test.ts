/**
 * @jest-environment jsdom
 */
import { renderHook } from "@testing-library/react";

import { novaChave, useChaveDeIdempotencia } from "@/lib/chave-idempotencia";

afterEach(() => jest.restoreAllMocks());

describe("novaChave", () => {
  it("gera códigos diferentes e aceitos pela API (8 a 80 caracteres simples)", () => {
    const chaves = new Set(Array.from({ length: 50 }, novaChave));
    expect(chaves.size).toBe(50);
    for (const c of chaves) expect(c).toMatch(/^[A-Za-z0-9._:-]{8,80}$/);
  });

  it("sem crypto.randomUUID (página http fora do localhost), cai em bytes aleatórios", () => {
    const original = globalThis.crypto.randomUUID;
    // @ts-expect-error simula o navegador sem a função
    globalThis.crypto.randomUUID = undefined;
    try {
      expect(novaChave()).toMatch(/^[0-9a-f]{32}$/);
    } finally {
      globalThis.crypto.randomUUID = original;
    }
  });
});

describe("useChaveDeIdempotencia", () => {
  it("devolve sempre o mesmo código até o pedido dar certo: duplo clique e reenvio levam a mesma chave", () => {
    const { result } = renderHook(() => useChaveDeIdempotencia());
    const primeira = result.current.atual();
    expect(result.current.atual()).toBe(primeira);
  });

  it("depois do sucesso, renovar() faz o próximo envio ser outro pedido", () => {
    const { result } = renderHook(() => useChaveDeIdempotencia());
    const primeira = result.current.atual();
    result.current.renovar();
    expect(result.current.atual()).not.toBe(primeira);
  });

  it("cada formulário tem a sua chave", () => {
    const a = renderHook(() => useChaveDeIdempotencia());
    const b = renderHook(() => useChaveDeIdempotencia());
    expect(a.result.current.atual()).not.toBe(b.result.current.atual());
  });
});
