/**
 * Usuários e senhas: regras espelhadas da API (para avisar enquanto a pessoa digita; quem decide é a API),
 * gerador de senha e os textos da auditoria. Funções puras.
 */
import { NOME_DO_PERFIL } from "@/lib/permissoes";
import type { Perfil } from "@/lib/tipos";

/** Mesmo mínimo da API (app/seguranca.py: SENHA_MINIMA). */
export const SENHA_MINIMA = 10;

export const PERFIS: Perfil[] = ["admin", "atendente", "leitor"];

export const DESCRICAO_DO_PERFIL: Record<Perfil, string> = {
  admin: "Tudo, inclusive apagar e gerenciar usuários.",
  atendente: "Cadastra e edita clientes e processos.",
  leitor: "Só consulta: não altera nada.",
};

/** Só admin entra com senha; os demais perfis entram só com o Google (mesma regra da API). */
export const temSenha = (perfil: Perfil) => perfil === "admin";

export type Erros = Record<string, string>;

export function validarSenha(senha: string, confirmacao?: string): Erros {
  const erros: Erros = {};
  if (senha.length < SENHA_MINIMA) erros.senha = `A senha precisa ter pelo menos ${SENHA_MINIMA} caracteres.`;
  else if (confirmacao !== undefined && confirmacao !== senha) erros.confirmacao = "As senhas não conferem.";
  return erros;
}

/** `comSenha`: só o administrador tem senha; para os outros perfis a senha nem é pedida. */
export function validarUsuarioNovo(
  v: { nome: string; email: string; senha: string },
  comSenha = true,
): Erros {
  const erros: Erros = {};
  if (!v.nome.trim()) erros.nome = "Informe o nome.";
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.email.trim())) erros.email = "E-mail inválido.";
  return comSenha ? { ...erros, ...validarSenha(v.senha) } : erros;
}

// sem caracteres que se confundem ao ditar ou ler (0/O, 1/l/I)
const ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";

/**
 * Senha aleatória para o primeiro acesso ou para redefinir. Usa o gerador criptográfico do navegador
 * (nunca Math.random), em grupos de 4 para ficar fácil de ditar: "Kq7m-Xa3P-tR9w".
 */
export function gerarSenha(
  grupos = 3,
  aleatorio: (n: number) => Uint32Array = (n) => crypto.getRandomValues(new Uint32Array(n)),
): string {
  const numeros = aleatorio(grupos * 4);
  const letras = Array.from(numeros, (n) => ALFABETO[n % ALFABETO.length]);
  return Array.from({ length: grupos }, (_, i) => letras.slice(i * 4, i * 4 + 4).join("")).join("-");
}

export function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/).filter(Boolean);
  if (partes.length === 0) return "?";
  const primeira = partes[0]![0] ?? "";
  const ultima = partes.length > 1 ? (partes[partes.length - 1]![0] ?? "") : "";
  return (primeira + ultima).toUpperCase();
}

// ---------------------------------------------------------------- auditoria

export type RegistroAuditoria = {
  id: number;
  usuario_id: number;
  feito_por_id: number | null;
  campo: string;
  valor_anterior: string | null;
  valor_novo: string | null;
  criado_em: string;
};

const perfil = (v: string | null) => (v && NOME_DO_PERFIL[v as Perfil]) || v || "—";
const situacao = (v: string | null) => (v === "True" ? "ativo" : v === "False" ? "inativo" : (v ?? "—"));

/** Frase de uma linha da auditoria: "Perfil: Atendente → Administrador". A senha nunca aparece. */
export function descreverAuditoria(r: RegistroAuditoria): string {
  switch (r.campo) {
    case "criado":
      return `Usuário criado como ${perfil(r.valor_novo)}`;
    case "perfil":
      return `Perfil: ${perfil(r.valor_anterior)} → ${perfil(r.valor_novo)}`;
    case "ativo":
      return r.valor_novo === "True" ? "Acesso reativado" : "Acesso desativado";
    case "nome":
      return `Nome: ${r.valor_anterior ?? "—"} → ${r.valor_novo ?? "—"}`;
    case "senha":
      if (r.valor_novo?.startsWith("removida")) return "Senha removida: passa a entrar só com o Google";
      return r.valor_novo === "redefinida"
        ? "Senha redefinida por um administrador"
        : "Trocou a própria senha";
    default:
      return `${r.campo}: ${situacao(r.valor_anterior)} → ${situacao(r.valor_novo)}`;
  }
}
