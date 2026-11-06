/** Preferência de animação: regra pura (testável sem navegador). */

export type PreferenciaMovimento = "sistema" | "ligado" | "reduzido";

export function lerValor(valor: string | null): PreferenciaMovimento {
  return valor === "ligado" || valor === "reduzido" ? valor : "sistema";
}

/**
 * As animações ficam paradas? "sistema" segue o "reduzir movimento" do sistema operacional (no Windows:
 * Acessibilidade > Efeitos visuais > Efeitos de animação); "ligado" e "reduzido" valem sobre ele.
 */
export function animacoesReduzidas(preferencia: PreferenciaMovimento, sistemaReduz: boolean): boolean {
  if (preferencia === "ligado") return false;
  if (preferencia === "reduzido") return true;
  return sistemaReduz;
}
