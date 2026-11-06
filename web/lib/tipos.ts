/** Formatos devolvidos pela API (Concept Visa Workflow, FastAPI). */

export type Perfil = "admin" | "atendente" | "leitor";

export type Usuario = {
  id: number;
  nome: string;
  email: string;
  ativo: boolean;
  perfil: Perfil;
};

export type TipoProcesso = "OBT" | "REN" | "PASS";

export type ResumoTipo = {
  total: number;
  por_situacao: Record<string, number>;
  por_resultado: Record<string, number>;
};

export type Resumo = Record<TipoProcesso, ResumoTipo>;
