/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: "node",
  rootDir: ".",
  testMatch: ["<rootDir>/tests/e2e/**/*.test.ts"],
  // `next dev` pode levar bem mais que 5s (padrão do Jest) pra compilar do
  // zero e responder ao primeiro request — esperarServidor (tests/e2e) tenta por até
  // ~80s (o CI começa sem cache do Next), então o timeout do hook precisa cobrir isso.
  testTimeout: 100000,
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
  },
  setupFiles: ["dotenv/config"],
  transform: {
    "^.+\\.tsx?$": [
      "ts-jest",
      {
        tsconfig: {
          module: "commonjs",
          moduleResolution: "node",
          jsx: "react-jsx",
        },
      },
    ],
  },
};
