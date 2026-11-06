/** @type {import('jest').Config} */
// Padrão da empresa (assets/jest.config.js), com dois ajustes de um front sem banco próprio:
// aceita testes .tsx de componente (ambiente jsdom por arquivo, via @jest-environment) e troca o
// pacote `server-only` por um vazio, porque o Jest não roda com a condição "react-server".
module.exports = {
  preset: "ts-jest",
  testEnvironment: "node",
  rootDir: ".",
  maxWorkers: 1,
  testMatch: ["<rootDir>/tests/**/*.test.ts", "<rootDir>/tests/**/*.test.tsx"],
  testPathIgnorePatterns: ["/node_modules/", "<rootDir>/tests/e2e/"],
  moduleNameMapper: {
    "^server-only$": "<rootDir>/tests/stubs/vazio.js",
    "^@/(.*)$": "<rootDir>/$1",
  },
  setupFiles: ["dotenv/config"],
  setupFilesAfterEnv: ["<rootDir>/tests/setup.ts"],
  transform: {
    "^.+\\.tsx?$": [
      "ts-jest",
      {
        tsconfig: {
          module: "commonjs",
          moduleResolution: "node",
          jsx: "react-jsx",
          esModuleInterop: true,
        },
      },
    ],
  },
  // motion (animações) é publicado como ESM: o ts-jest precisa transformá-lo também
  transformIgnorePatterns: ["/node_modules/(?!(motion|framer-motion|motion-dom|motion-utils)/)"],
};
