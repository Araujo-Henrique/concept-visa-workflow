import { cn } from "@/lib/utils";

/**
 * Nome "CONCEPT VISTOS" como na logo oficial: o O de CONCEPT é um anel com uma seta azul,
 * o O final de VISTOS é um globo azul com um avião. Texto real (acessível e nítido em qualquer tamanho).
 */
function OSeta() {
  return (
    <svg viewBox="0 0 100 100" className="inline-block h-[0.74em] w-[0.74em] align-baseline" aria-hidden>
      <path
        d="M 76 22 A 38 38 0 1 0 76 78"
        fill="none"
        stroke="currentColor"
        strokeWidth="17"
        strokeLinecap="butt"
      />
      <path d="M 46 20 L 80 50 L 46 80 L 35 69 L 56 50 L 35 31 Z" fill="var(--marca)" />
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
        C<OSeta />
        NCEPT
      </span>
      <span className="text-marca" aria-hidden>
        VIST
        <OGlobo />S
      </span>
    </span>
  );
}
