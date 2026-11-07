/** Nome do cookie que guarda o token da API. httpOnly: o JavaScript do navegador nunca o lê. */
export const COOKIE_SESSAO = "cv_sessao";

/**
 * Quando a sessão vence (milissegundos desde 1970). NÃO é httpOnly de propósito: não é segredo (o token
 * continua no cv_sessao) e o navegador precisa ler para renovar enquanto há uso e avisar antes de vencer.
 */
export const COOKIE_EXPIRA = "cv_expira";

/** Preferência de animação do usuário (localStorage), além do "reduzir movimento" do sistema. */
export const CHAVE_MOVIMENTO = "cv-movimento";
