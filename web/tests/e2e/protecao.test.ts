/**
 * Roda contra o `next dev` de verdade (npm run test:e2e). Não precisa da API: só confere a porta de entrada.
 */
const BASE = process.env.E2E_URL ?? "http://localhost:3000";

async function esperarServidor(tentativas = 60) {
  for (let i = 0; i < tentativas; i++) {
    try {
      const r = await fetch(`${BASE}/login`);
      if (r.ok) return;
    } catch {
      /* ainda subindo */
    }
    await new Promise((ok) => setTimeout(ok, 500));
  }
  throw new Error(`next dev não respondeu em ${BASE}`);
}

beforeAll(() => esperarServidor());

describe("sem login", () => {
  it("a página inicial manda para o login", async () => {
    const r = await fetch(`${BASE}/`, { redirect: "manual" });
    expect(r.status).toBe(307);
    expect(new URL(r.headers.get("location")!, BASE).pathname).toBe("/login");
  });

  it("guarda para onde a pessoa ia, para voltar depois de entrar", async () => {
    const r = await fetch(`${BASE}/processos?tipo=OBT`, { redirect: "manual" });
    const destino = new URL(r.headers.get("location")!, BASE);
    expect(destino.pathname).toBe("/login");
    expect(destino.searchParams.get("de")).toBe("/processos?tipo=OBT");
  });

  it("o login abre, com a identidade da Concept", async () => {
    const r = await fetch(`${BASE}/login`);
    const html = await r.text();
    expect(r.status).toBe(200);
    expect(html).toContain("Boas-vindas de volta");
    expect(html).toContain('lang="pt-BR"');
  });
});

describe("cookie inválido", () => {
  it("passa pela checagem otimista, mas a API recusa e a pessoa volta ao login", async () => {
    // o proxy só vê que o cookie existe; quem valida o token é a API (401 -> /login?expirou=1)
    const r = await fetch(`${BASE}/`, { headers: { Cookie: "cv_sessao=token-falso" }, redirect: "manual" });
    const html = await r.text();
    expect(r.status === 307 || html.includes("/login?expirou=1")).toBe(true);
  });
});
