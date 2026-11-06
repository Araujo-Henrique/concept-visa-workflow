import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
