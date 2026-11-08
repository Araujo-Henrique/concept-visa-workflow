import "server-only";

import { headers } from "next/headers";

/**
 * Quem abriu o site. Para a API, toda chamada vem do servidor do Next (127.0.0.1); sem repassar o IP real,
 * o limite de requisições da API trataria todo mundo como uma pessoa só. Vai no cabeçalho X-Cliente-IP, em
 * que a API só acredita quando a conexão vem da própria máquina (API_PROXIES_CONFIAVEIS).
 */
export const CABECALHO_IP = "X-Cliente-IP";

/**
 * O IP no X-Forwarded-For. Vale o ÚLTIMO da lista: é o que o nosso intermediário (ngrok, nginx) viu na
 * conexão. Os anteriores vêm de quem fez o pedido e podem ser inventados para escapar do limite. Sem
 * intermediário, o próprio Next preenche o cabeçalho com o endereço da conexão.
 */
export function ipDoEncaminhamento(encaminhado: string | null | undefined): string | null {
  const ultimo = encaminhado?.split(",").at(-1)?.trim();
  return ultimo ? ultimo.slice(0, 64) : null;
}

/** Cabeçalho para mandar à API junto com a chamada (vazio quando não dá para saber o IP). */
export async function cabecalhoDoCliente(): Promise<Record<string, string>> {
  const ip = ipDoEncaminhamento((await headers()).get("x-forwarded-for"));
  return ip ? { [CABECALHO_IP]: ip } : {};
}
