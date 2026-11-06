/** Traduz respostas de erro da API em mensagens para quem está usando a tela. Funções puras (testáveis). */

export class ErroApi extends Error {
  constructor(
    public status: number,
    mensagem: string,
  ) {
    super(mensagem);
    this.name = "ErroApi";
  }
}

const PADRAO: Record<number, string> = {
  400: "Pedido inválido.",
  401: "Sua sessão expirou. Entre novamente.",
  403: "Seu perfil não permite esta ação.",
  404: "Não encontrei esse registro.",
  409: "Conflito: o registro mudou ou já existe.",
  422: "Confira os dados informados.",
  503: "O servidor de dados está indisponível. Tente de novo em instantes.",
};

type ErroDeCampo = { loc?: (string | number)[]; msg?: string };

/** `detail` da API: texto (regras de negócio, já em português) ou lista do Pydantic (422). */
export function mensagemDeErro(status: number, detail: unknown): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    const campos = (detail as ErroDeCampo[])
      .map((e) => e.loc?.filter((p) => p !== "body").join("."))
      .filter(Boolean);
    if (campos.length)
      return `Confira ${campos.length > 1 ? "os campos" : "o campo"}: ${[...new Set(campos)].join(", ")}.`;
  }
  return PADRAO[status] ?? "Algo deu errado. Tente de novo.";
}

/** Destino depois do login: só caminhos internos (evita redirecionar para outro site). */
export function destinoSeguro(destino: string | null | undefined): string {
  if (!destino || !destino.startsWith("/") || destino.startsWith("//") || destino.startsWith("/\\"))
    return "/";
  if (destino.startsWith("/login")) return "/";
  return destino;
}
