/**
 * @jest-environment jsdom
 */
import { act } from "react";
import { hydrateRoot } from "react-dom/client";

import { CenaVoo } from "@/components/login/cena-voo";
import { Provedores } from "@/components/provedores";
import { CHAVE_MOVIMENTO } from "@/lib/constantes";
import { animacoesReduzidas, lerValor } from "@/lib/movimento";

describe("preferência de animação", () => {
  it("'sistema' segue o sistema; 'ligado' e 'reduzido' valem sobre ele", () => {
    expect(animacoesReduzidas("sistema", true)).toBe(true);
    expect(animacoesReduzidas("sistema", false)).toBe(false);
    expect(animacoesReduzidas("ligado", true)).toBe(false); // a pessoa liberou mesmo com o Windows reduzindo
    expect(animacoesReduzidas("reduzido", false)).toBe(true);
  });

  it("valor desconhecido ou vazio vira 'sistema'", () => {
    expect(lerValor(null)).toBe("sistema");
    expect(lerValor("qualquer")).toBe("sistema");
    expect(lerValor("ligado")).toBe("ligado");
  });
});

// ---- regressão: "Hydration failed" no login quando o Windows está com as animações desligadas

function simularSistema(reduz: boolean) {
  window.matchMedia = jest.fn().mockImplementation((media: string) => ({
    matches: media.includes("reduce") ? reduz : false,
    media,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
  }));
}

beforeAll(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  // jsdom não mede SVG: a posição do avião ao longo da rota usa estas funções
  Object.assign(SVGElement.prototype, {
    getTotalLength: () => 100,
    getPointAtLength: (d: number) => ({ x: d, y: d }),
  });
});

beforeEach(() => localStorage.clear());

/**
 * HTML como o servidor do Next mandaria: lá não existe "reduzir movimento" do sistema. Módulos isolados,
 * porque a biblioteca de animação guarda essa resposta em cache (e o navegador abaixo precisa da sua).
 */
function htmlDoServidor(): string {
  const reduzNoNavegador = window.matchMedia;
  simularSistema(false);
  let html = "";
  jest.isolateModules(() => {
    const React = require("react");
    const { renderToString: renderizar } = require("react-dom/server");
    const { Provedores: P } = require("@/components/provedores");
    const { CenaVoo: C } = require("@/components/login/cena-voo");
    html = renderizar(React.createElement(P, null, React.createElement(C)));
  });
  window.matchMedia = reduzNoNavegador;
  return html;
}

async function hidratar() {
  const pagina = (
    <Provedores>
      <CenaVoo />
    </Provedores>
  );
  const container = document.createElement("div");
  container.innerHTML = htmlDoServidor();
  document.body.appendChild(container);
  const erros: unknown[] = [];
  await act(async () => {
    hydrateRoot(container, pagina, { onRecoverableError: (erro) => erros.push(erro) });
  });
  return { container, erros };
}

describe("cena do login com 'reduzir movimento' no sistema", () => {
  it("hidrata sem erro e oferece 'Ver animação'", async () => {
    simularSistema(true);
    const { container, erros } = await hidratar();
    expect(erros).toEqual([]);
    expect(container.textContent).toContain("Ver animação");
  });

  it("com 'Sempre ligadas' escolhido, anima mesmo com o sistema reduzindo", async () => {
    simularSistema(true);
    localStorage.setItem(CHAVE_MOVIMENTO, "ligado");
    const { container, erros } = await hidratar();
    expect(erros).toEqual([]);
    expect(container.textContent).not.toContain("Ver animação");
  });
});
