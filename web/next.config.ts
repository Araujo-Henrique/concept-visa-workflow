import type { NextConfig } from "next";

/**
 * Cabeçalhos de segurança em todas as respostas:
 *  - ninguém mostra o sistema dentro de um <iframe> de outro site (golpe do clique escondido);
 *  - o navegador não "adivinha" o tipo de um arquivo;
 *  - o endereço completo (com filtros e ids) não vaza para outros sites;
 *  - câmera, microfone e localização desligados;
 *  - HSTS: depois da primeira visita por HTTPS, o navegador só usa HTTPS (em http://localhost ele ignora);
 *  - CSP básica: sem plugins, sem <base> trocado e formulários só para o próprio site. (Limitar os scripts
 *    exige nonce em cada página; fica para quando for necessário.)
 */
export const CABECALHOS_DE_SEGURANCA = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  { key: "Strict-Transport-Security", value: "max-age=31536000" },
  {
    key: "Content-Security-Policy",
    value: "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'",
  },
];

const nextConfig: NextConfig = {
  // "standalone" gera .next/standalone (a imagem Docker leva só o necessário e roda `node server.js`), mas o
  // `next start` não funciona com ele. Por isso só o Docker liga (NEXT_OUTPUT=standalone no web/Dockerfile);
  // `npm run dev` e `npm run publicar` seguem sem ele.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  poweredByHeader: false, // não anuncia que é Next.js (e a versão) para quem procura alvo
  headers: async () => [{ source: "/:path*", headers: CABECALHOS_DE_SEGURANCA }],
  cacheComponents: true,
  // em desenvolvimento, abrir por 127.0.0.1 (além de localhost) não bloqueia os arquivos do dev server
  allowedDevOrigins: ["127.0.0.1"],
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
