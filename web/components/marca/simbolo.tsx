import { cn } from "@/lib/utils";

/**
 * Símbolo da Concept Vistos (pin de destino): anel azul aberto embaixo + "V" preto que lembra um check.
 * Redesenhado em vetor a partir da logo oficial (mesma geometria, coordenadas normalizadas).
 */
export const SIMBOLO_VIEWBOX = "0 0 610 725";
export const ANEL = "M 103 515 A 295 295 0 1 1 510 515 L 425 431 A 175 175 0 1 0 188 431 Z";
export const SETA = "M 145 557 L 230 473 L 306 550 L 384 473 L 468 557 L 306 718 Z";

type Props = {
  className?: string;
  /** "cor": anel azul + seta tinta; "claro": seta clara para fundos escuros; "mono": tudo currentColor */
  variante?: "cor" | "claro" | "mono";
  titulo?: string;
};

export function Simbolo({ className, variante = "cor", titulo = "Concept Vistos" }: Props) {
  const anel = variante === "mono" ? "fill-current" : "fill-marca";
  // "cor": seta tinta no claro e papel no escuro (senão some no fundo #050510)
  const seta =
    variante === "mono" ? "fill-current" : variante === "claro" ? "fill-papel" : "fill-tinta dark:fill-papel";
  return (
    <svg viewBox={SIMBOLO_VIEWBOX} className={cn("h-8 w-auto", className)} role="img" aria-label={titulo}>
      <path d={ANEL} className={anel} />
      <path d={SETA} className={seta} />
    </svg>
  );
}
