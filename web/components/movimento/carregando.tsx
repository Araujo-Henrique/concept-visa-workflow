import { cn } from "@/lib/utils";

/**
 * Carregamento da marca: o globo azul do "O" de VISTOS com um avião dando a volta nele.
 * Só CSS (funciona mesmo antes do JavaScript carregar); parado com "reduzir movimento".
 */
export function Carregando({ texto = "Carregando…", className }: { texto?: string; className?: string }) {
  return (
    <div role="status" className={cn("flex flex-col items-center justify-center gap-4", className)}>
      <div className="relative size-16">
        <span className="absolute inset-2 rounded-full bg-marca/90" />
        <span className="absolute inset-0 animate-spin [animation-duration:1.6s]">
          <svg
            viewBox="-20 -20 40 40"
            className="absolute -top-2 left-1/2 size-5 -translate-x-1/2"
            aria-hidden
          >
            <path
              d="M 18 0 L 6 -3 L -2 -14 L -7 -14 L -3 -3 L -12 -2 L -16 -7 L -19 -7 L -17 0 L -19 7 L -16 7 L -12 2 L -3 3 L -7 14 L -2 14 L 6 3 Z"
              className="fill-foreground"
            />
          </svg>
        </span>
      </div>
      <p className="text-sm text-muted-foreground">{texto}</p>
    </div>
  );
}
