"use client";

import { AnimatePresence, motion, type Variants } from "motion/react";
import { BookOpen, IdCard, Stamp, Users } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Capa, PAPEL } from "@/components/passaporte/paginas";
import { useMovimento } from "@/components/provedores";
import type { LinhaPainel } from "@/lib/tipos";
import { cn } from "@/lib/utils";

export type IdPagina = "capa" | "dados" | "pessoas" | "historico";

export const PAGINAS: { id: IdPagina; rotulo: string; icone: typeof IdCard }[] = [
  { id: "capa", rotulo: "Capa", icone: BookOpen },
  { id: "dados", rotulo: "Dados", icone: IdCard },
  { id: "pessoas", rotulo: "Pessoas", icone: Users },
  { id: "historico", rotulo: "Carimbos", icone: Stamp },
];

const indice = (id: IdPagina) => PAGINAS.findIndex((p) => p.id === id);
const CURVA = [0.4, 0, 0.2, 1] as const;

/**
 * Página que vira: para frente, a página atual gira pela lombada (esquerda) e revela a próxima por baixo;
 * para trás, a anterior volta girando por cima. Com "reduzir movimento", só troca.
 */
const virar: Variants = {
  entra: (direcao: number) =>
    direcao > 0 ? { rotateY: 0, opacity: 1, zIndex: 0 } : { rotateY: -105, opacity: 0, zIndex: 2 },
  parada: { rotateY: 0, opacity: 1, zIndex: 1, transition: { duration: 0.6, ease: CURVA } },
  sai: (direcao: number) =>
    direcao > 0
      ? { rotateY: -105, opacity: 0, zIndex: 2, transition: { duration: 0.6, ease: CURVA } }
      : { opacity: 0, zIndex: 0, transition: { duration: 0.6 } },
};

export function Passaporte({
  linha,
  pagina,
  direcao,
  aoMudar,
  paginas,
}: {
  linha: LinhaPainel;
  pagina: IdPagina;
  direcao: number;
  aoMudar: (id: IdPagina) => void;
  paginas: Record<Exclude<IdPagina, "capa">, ReactNode>;
}) {
  const { reduzido } = useMovimento();
  const [capaAberta, setCapaAberta] = useState(false);

  return (
    <div className="flex flex-col gap-3 lg:flex-row-reverse lg:items-start lg:gap-0">
      {/* abas como as marcações de índice na lateral de um caderno */}
      <div
        role="tablist"
        aria-label="Páginas do passaporte"
        className="grid grid-cols-4 gap-1 sm:flex lg:mt-10 lg:flex-col"
      >
        {PAGINAS.map(({ id, rotulo, icone: Icone }) => {
          const atual = id === pagina;
          return (
            <button
              key={id}
              role="tab"
              type="button"
              id={`aba-${id}`}
              aria-selected={atual}
              aria-controls="pagina-passaporte"
              onClick={() => !atual && aoMudar(id)}
              className={cn(
                // no celular: ícone em cima do nome e as 4 abas dividem a largura (antes passavam da tela)
                "flex flex-col items-center justify-center gap-1 rounded-lg px-1 py-2 text-[11px] font-medium transition-all sm:flex-row sm:gap-2 sm:px-3 sm:text-sm lg:rounded-l-none lg:rounded-r-xl lg:py-3",
                atual
                  ? "bg-tinta text-papel lg:translate-x-1"
                  : "bg-muted text-muted-foreground hover:bg-marca-suave hover:text-foreground",
              )}
            >
              <Icone className={cn("size-4", atual && "text-marca")} /> {rotulo}
            </button>
          );
        })}
      </div>

      <div
        id="pagina-passaporte"
        role="tabpanel"
        aria-labelledby={`aba-${pagina}`}
        // isolate + overflow: a página (e a capa) vira dentro do livro, sem passar por cima do menu lateral
        className="relative isolate grid flex-1 grid-cols-1 overflow-hidden rounded-2xl shadow-[0_18px_40px_-20px_rgba(5,5,16,0.35)] [perspective:1800px] [&>*]:[grid-area:1/1]"
      >
        <AnimatePresence initial={false} custom={direcao}>
          <motion.section
            key={pagina}
            custom={direcao}
            variants={virar}
            initial="entra"
            animate="parada"
            exit="sai"
            style={{ transformOrigin: "left center", backfaceVisibility: "hidden" }}
            className={cn(
              "min-h-[560px] rounded-2xl border",
              pagina === "capa" ? "border-0 p-0" : cn(PAPEL, "p-6 sm:p-8"),
            )}
          >
            {pagina === "capa" ? <Capa linha={linha} /> : paginas[pagina]}
          </motion.section>
        </AnimatePresence>

        {/* ao entrar, a capa se abre sobre a página de dados (uma vez; sem animação, nem aparece) */}
        {!reduzido && !capaAberta && pagina !== "capa" && (
          <motion.div
            aria-hidden
            initial={{ rotateY: 0 }}
            animate={{ rotateY: -110, opacity: 0 }}
            transition={{ delay: 0.35, duration: 0.9, ease: CURVA }}
            onAnimationComplete={() => setCapaAberta(true)}
            style={{ transformOrigin: "left center", zIndex: 5 }}
          >
            <Capa linha={linha} />
          </motion.div>
        )}
      </div>
    </div>
  );
}

/** Direção do virar de página: para frente (1) ou para trás (-1). */
export function direcaoEntre(de: IdPagina, para: IdPagina): number {
  return indice(para) >= indice(de) ? 1 : -1;
}
