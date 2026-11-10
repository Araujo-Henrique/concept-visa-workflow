import type { Perfil } from "@/lib/tipos";

/**
 * Espelho da regra da API (app/permissoes.py), só para mostrar ou esconder botões.
 * Quem decide de verdade continua sendo a API (401/403): esconder um botão não protege nada.
 */
/** `apagar_cliente`: excluir um cliente (atendente também: o admin restaura). `apagar`: o resto, só admin. */
export type Acao = "ler" | "escrever" | "apagar" | "apagar_cliente" | "administrar";

const PERMISSOES: Record<Perfil, readonly Acao[]> = {
  leitor: ["ler"],
  atendente: ["ler", "escrever", "apagar_cliente"],
  admin: ["ler", "escrever", "apagar", "apagar_cliente", "administrar"],
};

export function pode(perfil: string | null | undefined, acao: Acao): boolean {
  // perfil desconhecido não pode nada (hasOwn: "constructor" e afins não contam como perfil)
  if (!perfil || !Object.hasOwn(PERMISSOES, perfil)) return false;
  return PERMISSOES[perfil as Perfil].includes(acao);
}

export const NOME_DO_PERFIL: Record<Perfil, string> = {
  admin: "Administrador",
  atendente: "Atendente",
  leitor: "Leitor",
};
