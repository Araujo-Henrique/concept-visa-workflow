/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";

import { rota } from "@/components/login/cena-voo";
import { Logotipo } from "@/components/marca/logotipo";
import { Simbolo } from "@/components/marca/simbolo";
import { iniciais } from "@/components/shell/menu-usuario";

jest.mock("@/app/acoes/auth", () => ({ sair: jest.fn(), entrar: jest.fn() }));

describe("marca", () => {
  it("logo e símbolo são lidos como 'Concept Vistos' por leitores de tela", () => {
    render(
      <>
        <Logotipo />
        <Simbolo />
      </>,
    );
    expect(screen.getAllByRole("img", { name: "Concept Vistos" })).toHaveLength(2);
  });
});

describe("cena do login", () => {
  it("a rota é um arco que começa na origem e termina no destino, erguido acima dos dois", () => {
    const d = rota(190, 448, 560, 150);
    const [, x0, y0, cx, cy, x1, y1] = d.match(/M (\S+) (\S+) Q (\S+) (\S+) (\S+) (\S+)/)!.map(Number);
    expect([x0, y0, x1, y1]).toEqual([190, 448, 560, 150]);
    expect(cx).toBe(375);
    expect(cy).toBeLessThan(150); // acima do ponto mais alto
  });
});

describe("menu do usuário", () => {
  it.each([
    ["Henrique Araujo", "HA"],
    ["Ana", "A"],
    ["  maria da silva souza ", "MS"],
  ])("iniciais de %s = %s", (nome, esperado) => {
    expect(iniciais(nome)).toBe(esperado);
  });
});
