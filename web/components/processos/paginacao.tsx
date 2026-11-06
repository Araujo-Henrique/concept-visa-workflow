"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { useNavegacao } from "@/components/processos/area-processos";
import { POR_PAGINA, urlDosFiltros, type Filtros } from "@/lib/processos";

export function Paginacao({ filtros, total }: { filtros: Filtros; total: number }) {
  const { navegar } = useNavegacao();
  if (total === 0) return null;
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));
  const inicio = (filtros.pagina - 1) * POR_PAGINA + 1;
  const fim = Math.min(total, filtros.pagina * POR_PAGINA);
  const ir = (pagina: number) => navegar(urlDosFiltros({ ...filtros, pagina }));

  return (
    <nav aria-label="Páginas" className="mt-4 flex items-center justify-between text-sm">
      <p className="text-muted-foreground">
        {inicio.toLocaleString("pt-BR")}–{fim.toLocaleString("pt-BR")} de{" "}
        <strong className="text-foreground">{total.toLocaleString("pt-BR")}</strong>
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={filtros.pagina <= 1}
          onClick={() => ir(filtros.pagina - 1)}
          className="flex h-9 items-center gap-1 rounded-lg border bg-card px-3 disabled:opacity-40"
        >
          <ChevronLeft className="size-4" /> Anterior
        </button>
        <span className="px-2 tabular-nums text-muted-foreground">
          {filtros.pagina} / {paginas}
        </span>
        <button
          type="button"
          disabled={filtros.pagina >= paginas}
          onClick={() => ir(filtros.pagina + 1)}
          className="flex h-9 items-center gap-1 rounded-lg border bg-card px-3 disabled:opacity-40"
        >
          Próxima <ChevronRight className="size-4" />
        </button>
      </div>
    </nav>
  );
}
