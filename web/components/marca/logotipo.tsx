import { ANEL, SETA } from "@/components/marca/simbolo";
import { cn } from "@/lib/utils";

/**
 * Nome "CONCEPT VISTOS" como na logo oficial: o C inicial de CONCEPT é o próprio símbolo (pin) deitado, apontando
 * para a direita (anel na cor do texto, "V" azul na abertura); o O final de VISTOS é um globo azul com avião.
 * Texto real (acessível e nítido em qualquer tamanho).
 */
function CSimbolo() {
  // mesma geometria do símbolo (viewBox 610 x 725), girada -90°: (x, y) -> (y, -x)
  return (
    <svg
      viewBox="0 -612 728 616"
      className="mx-[0.02em] inline-block h-[0.74em] w-[0.875em] align-baseline"
      aria-hidden
    >
      <g transform="rotate(-90)">
        <path d={ANEL} fill="currentColor" />
        <path d={SETA} fill="var(--marca)" />
      </g>
    </svg>
  );
}

function OGlobo() {
  return (
    <svg viewBox="0 0 100 100" className="inline-block h-[0.74em] w-[0.74em] align-baseline" aria-hidden>
      <circle cx="50" cy="50" r="46" fill="var(--marca)" />
      {/* avião em diagonal, subindo */}
      <path
        d="M 18 0 L 6 -3 L -2 -14 L -7 -14 L -3 -3 L -12 -2 L -16 -7 L -19 -7 L -17 0 L -19 7 L -16 7 L -12 2 L -3 3 L -7 14 L -2 14 L 6 3 Z"
        transform="translate(50 50) rotate(-35) scale(1.75)"
        fill="#050510"
      />
    </svg>
  );
}

type Props = { className?: string; claro?: boolean; empilhado?: boolean };

export function Logotipo({ className, claro = false, empilhado = true }: Props) {
  return (
    <span
      className={cn(
        "font-heading font-extrabold leading-[0.95] tracking-[0.06em] select-none",
        empilhado ? "inline-flex flex-col" : "inline-flex gap-[0.3em]",
        className,
      )}
      role="img"
      aria-label="Concept Vistos"
    >
      <span className={claro ? "text-papel" : "text-tinta dark:text-papel"} aria-hidden>
        <CSimbolo />
        ONCEPT
      </span>
      <span className="text-marca" aria-hidden>
        VIST
        <OGlobo />S
      </span>
    </span>
  );
}
