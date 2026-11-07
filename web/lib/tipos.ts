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

/** Uma linha do painel (view vw_painel_processos): cada tipo traz só os campos que lhe pertencem. */
type LinhaBase = {
  processo_id: number;
  situacao: string;
  cliente_id: number;
  cliente: string;
  telefone: string | null;
  grupo: string | null;
  titular: string | null;
  n_solicitantes: number;
  solicitantes: string;
  resultado_geral: "Processando" | "Aprovado" | "Negado" | "Parcial";
  n_formularios: number;
  atualizado_em: string;
};
export type LinhaOBT = LinhaBase & {
  tipo: "OBT";
  consulado: string | null;
  data_casv: string | null;
  data_entrevista: string | null;
  codigo_rastreio: string | null;
  orientacao: string | null;
  orientacao_data: string | null;
  orientacao_por: string | null;
};
export type LinhaREN = LinhaBase & {
  tipo: "REN";
  consulado: string | null;
  data_casv: string | null;
  data_despacho: string | null;
  codigo_rastreio: string | null;
};
export type LinhaPASS = LinhaBase & { tipo: "PASS"; data_pf: string | null; prazo_pf: string | null };
export type LinhaPainel = LinhaOBT | LinhaREN | LinhaPASS;

export type Formulario = {
  id: number;
  solicitante_id: number;
  codigo: string;
  status: string;
  observacao: string | null;
};

export type Solicitante = {
  id: number;
  processo_id: number;
  nome: string;
  titular: boolean;
  resultado: "Processando" | "Aprovado" | "Negado";
  formularios: Formulario[];
};

/** GET /processos-obt|ren|pass/{id}: campos comuns + os do tipo (lidos como registro). */
export type ProcessoDetalhe = {
  id: number;
  tipo: TipoProcesso;
  cliente_id: number;
  situacao: string;
  processo_anterior_id: number | null;
  criado_em: string;
  atualizado_em: string;
  observacao: string | null;
  solicitantes: Solicitante[];
} & Record<string, unknown>;

export type Evento = {
  id: number;
  processo_id: number;
  usuario_id: number | null;
  usuario_nome: string | null;
  tipo: "criado" | "situacao_alterada" | "reaberto";
  situacao_anterior: string | null;
  situacao_nova: string | null;
  motivo: string | null;
  criado_em: string;
};

export type Referencias = {
  situacoes: Record<TipoProcesso, string[]>;
  consulados: string[];
  rascunho: string[];
  status_ds: string[];
  resultado: string[];
  orientacao: string[];
  monitoramento: string[];
  docs_ren: string[];
  perfis: Perfil[];
  usuarios: { id: number; nome: string }[];
};

export type Cliente = {
  id: number;
  nome: string;
  email: string | null;
  telefone: string | null;
  grupo: string | null;
};

export type ClienteLista = Cliente & { n_processos: number };

export type UsuarioResumo = { id: number; nome: string };
