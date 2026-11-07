/**
 * Formulários de cliente e de processo: valores da tela (sempre texto, "" = vazio), regras e o corpo que vai
 * para a API. As regras espelham as da API para avisar enquanto a pessoa digita; quem decide é a API.
 */
import type { TipoProcesso } from "@/lib/tipos";

export type Valores = Record<string, string>;
export type Erros = Record<string, string>;

// ---------------------------------------------------------------- telefone

/** "41999990001" -> "(41) 99999-0001"; fixo com 10 dígitos -> "(41) 3333-0001". */
export function formatarTelefone(digitos: string | null | undefined): string {
  if (!digitos) return "—";
  const d = digitos.replace(/\D/g, "");
  if (d.length === 11) return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
  if (d.length === 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return d;
}

/** Link do WhatsApp (a API guarda sem o 55 do Brasil). */
export function linkWhatsapp(digitos: string | null | undefined): string | null {
  const d = (digitos ?? "").replace(/\D/g, "");
  return d.length >= 10 ? `https://wa.me/55${d}` : null;
}

// ---------------------------------------------------------------- cliente

export const CAMPOS_CLIENTE = ["nome", "email", "telefone", "grupo"] as const;

export function validarCliente(v: Valores): Erros {
  const erros: Erros = {};
  if (!v.nome?.trim()) erros.nome = "Informe o nome do cliente.";
  if (v.email?.trim() && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.email.trim())) erros.email = "E-mail inválido.";
  const digitos = (v.telefone ?? "").replace(/\D/g, "");
  if (digitos && (digitos.length < 10 || digitos.length > 13))
    erros.telefone = "Telefone com DDD: 10 ou 11 dígitos.";
  return erros;
}

/** Corpo para a API: texto aparado, e-mail em minúsculas, vazio vira null. */
export function corpoCliente(v: Valores) {
  const texto = (campo: string) => v[campo]?.trim() || null;
  return {
    nome: v.nome?.trim() ?? "",
    email: texto("email")?.toLowerCase() ?? null,
    telefone: texto("telefone"),
    grupo: texto("grupo"),
  };
}

// ---------------------------------------------------------------- processo

/** Campos editáveis de cada tipo (a situação muda pela rota do processo, não pelo formulário). */
export const CAMPOS_DO_TIPO: Record<TipoProcesso, string[]> = {
  OBT: [
    "consulado",
    "data_casv",
    "data_entrevista",
    "data_vencimento_taxa",
    "status_rascunho",
    "orientacao",
    "orientacao_data",
    "orientacao_por_id",
    "monitoramento",
    "codigo_rastreio",
    "observacao",
  ],
  REN: [
    "consulado",
    "data_casv",
    "docs",
    "status_rascunho",
    "endereco",
    "codigo_rastreio",
    "despachado_em",
    "observacao",
  ],
  PASS: ["data_pf", "prazo_pf", "observacao"],
};

const CAMPOS_DATA = new Set([
  "data_casv",
  "data_entrevista",
  "data_vencimento_taxa",
  "orientacao_data",
  "data_pf",
  "prazo_pf",
  "despachado_em",
]);

/** Valores iniciais de um processo novo (os mesmos padrões da API). */
export function valoresIniciais(tipo: TipoProcesso): Valores {
  const base: Valores = Object.fromEntries(CAMPOS_DO_TIPO[tipo].map((c) => [c, ""]));
  if (tipo === "OBT")
    Object.assign(base, { status_rascunho: "Pendente", orientacao: "Pendente", monitoramento: "Ativo" });
  if (tipo === "REN") Object.assign(base, { status_rascunho: "Pendente", docs: "Pendente" });
  return base;
}

/** Valores da tela a partir do processo gravado (para editar). */
export function valoresDoProcesso(tipo: TipoProcesso, processo: Record<string, unknown>): Valores {
  return Object.fromEntries(
    CAMPOS_DO_TIPO[tipo].map((c) => {
      const v = processo[c];
      return [
        c,
        v === null || v === undefined ? "" : String(v).slice(0, CAMPOS_DATA.has(c) ? 10 : undefined),
      ];
    }),
  );
}

/**
 * Regras entre campos. Ao editar (`alterados` informado), a do consulado só vale se a edição mexe no
 * consulado ou nas datas: os processos importados com "N/D" têm data e consulado vazio (igual à API).
 */
export function validarProcesso(tipo: TipoProcesso, v: Valores, alterados?: Set<string>): Erros {
  const erros: Erros = {};
  const mexeu = (...campos: string[]) => !alterados || campos.some((c) => alterados.has(c));
  if (tipo === "OBT") {
    if (v.orientacao === "Agendada" && !v.orientacao_data)
      erros.orientacao_data = "Orientação agendada pede a data.";
    if (
      (v.data_casv || v.data_entrevista) &&
      !v.consulado &&
      mexeu("consulado", "data_casv", "data_entrevista")
    )
      erros.consulado = "Com data de CASV ou entrevista, informe o consulado.";
  }
  if (tipo === "REN" && v.data_casv && !v.consulado && mexeu("consulado", "data_casv"))
    erros.consulado = "Com data de CASV, informe o consulado.";
  if (tipo === "PASS" && v.data_pf && v.prazo_pf && v.prazo_pf < v.data_pf)
    erros.prazo_pf = "O prazo não pode ser antes da data da PF.";
  return erros;
}

function valorDaApi(campo: string, valor: string): string | number | null {
  if (valor === "") return null;
  if (campo === "orientacao_por_id") return Number(valor);
  return CAMPOS_DATA.has(campo) ? valor : valor.trim() || null;
}

/** Corpo do POST (processo novo). Campos de seleção com valor padrão sempre vão; vazios viram null. */
export function corpoProcessoNovo(
  tipo: TipoProcesso,
  clienteId: number,
  situacao: string,
  v: Valores,
  extras: string[],
) {
  return {
    cliente_id: clienteId,
    situacao,
    solicitantes_extras: extras.map((n) => n.trim()).filter(Boolean),
    ...Object.fromEntries(CAMPOS_DO_TIPO[tipo].map((c) => [c, valorDaApi(c, v[c] ?? "")])),
  };
}

/** Corpo do PATCH: só o que mudou em relação ao gravado. */
export function corpoEdicao(tipo: TipoProcesso, antes: Valores, depois: Valores) {
  const mudou = CAMPOS_DO_TIPO[tipo].filter((c) => (antes[c] ?? "") !== (depois[c] ?? ""));
  return Object.fromEntries(mudou.map((c) => [c, valorDaApi(c, depois[c] ?? "")]));
}

// ---------------------------------------------------------------- DS-160

export const PADRAO_DS160 = /^AA00[A-Z0-9]{6}$/;

export function normalizarCodigo(codigo: string): string {
  return codigo.replace(/\s/g, "").toUpperCase();
}
