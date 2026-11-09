import { useRef } from "react";

/**
 * Código único de um pedido de criação, enviado à API no cabeçalho Idempotency-Key. Nasce AQUI, no navegador,
 * uma vez por formulário: se a pessoa clicar duas vezes ou a rede reenviar, os dois pedidos levam o MESMO
 * código e a API cria uma vez só. (Gerar o código no servidor não adiantaria: cada clique ganharia um diferente.)
 */
export function novaChave(): string {
  const c = globalThis.crypto;
  if (typeof c?.randomUUID === "function") return c.randomUUID();
  // navegador sem randomUUID (página http fora do localhost): 16 bytes aleatórios em hexadecimal
  const bytes = c.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * A chave do formulário. `atual()` devolve sempre a mesma enquanto o pedido não der certo (reenviar depois de
 * um erro é seguro: a API libera a chave em erro). Depois do sucesso, chame `renovar()`: o próximo envio
 * é outro pedido.
 */
export function useChaveDeIdempotencia() {
  const chave = useRef<string | null>(null);
  return {
    atual: () => (chave.current ??= novaChave()),
    renovar: () => {
      chave.current = null;
    },
  };
}
