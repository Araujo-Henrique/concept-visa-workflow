import { ArrowRight, PlaneTakeoff } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import { contarPorEvento, EVENTOS, ORDEM_DOS_EVENTOS, rotuloDoDia } from "@/lib/agenda";
import { rotuloSituacao } from "@/lib/formatos";
import type { AgendaItem } from "@/lib/tipos";
import { cn } from "@/lib/utils";

export const DIAS_DO_PAINEL = 7;
const LINHAS = 10;

const COLUNAS =
  "grid grid-cols-[6.25rem_minmax(0,1fr)_3.5rem] items-center gap-3 sm:grid-cols-[7rem_6.5rem_minmax(0,1fr)_5rem_4.5rem_9rem]";

/**
 * Painel de embarque, como o letreiro de partidas do aeroporto: os próximos compromissos da semana.
 * As linhas "viram" como as plaquinhas do letreiro ao chegar (só CSS, desligado em "reduzir movimento").
 */
export function PainelEmbarque({ itens, hoje }: { itens?: AgendaItem[]; hoje?: string }) {
  const contagem = itens ? contarPorEvento(itens) : {};
  const deHoje = itens && hoje ? itens.filter((i) => i.data.startsWith(hoje)).length : 0;
  return (
    <section
      className="overflow-hidden rounded-2xl bg-tinta text-papel shadow-lg ring-1 ring-white/5"
      aria-labelledby="titulo-painel"
      aria-busy={!itens}
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
        <div className="flex items-center gap-3">
          <PlaneTakeoff className="size-5 text-marca" aria-hidden />
          <div>
            <h2 id="titulo-painel" className="font-heading text-sm font-bold tracking-[0.25em] uppercase">
              Próximos embarques
            </h2>
            <p className="text-xs text-papel/60">
              {itens
                ? `${deHoje} hoje · ${itens.length} nos próximos ${DIAS_DO_PAINEL} dias`
                : "Carregando o letreiro…"}
            </p>
          </div>
        </div>
        {itens && (
          <ul className="flex flex-wrap gap-1.5" aria-label="Compromissos da semana por tipo">
            {ORDEM_DOS_EVENTOS.filter((e) => contagem[e]).map((e) => (
              <li
                key={e}
                className="inline-flex items-center gap-1.5 rounded-full bg-white/5 px-2.5 py-1 text-xs"
              >
                <span
                  className={cn("size-2 rounded-full", e === "entrevista" ? "bg-papel" : EVENTOS[e].ponto)}
                  aria-hidden
                />
                {EVENTOS[e].rotulo}
                <strong className="tabular-nums">{contagem[e]}</strong>
              </li>
            ))}
          </ul>
        )}
      </header>

      <div
        className={cn(
          COLUNAS,
          "px-5 pt-3 pb-2 font-heading text-[10px] font-bold tracking-[0.2em] text-papel/50 uppercase",
        )}
        aria-hidden
      >
        <span>Dia</span>
        <span className="hidden sm:block">Embarque</span>
        <span>Passageiro</span>
        <span className="hidden sm:block">Voo</span>
        <span className="text-right sm:text-left">Portão</span>
        <span className="hidden sm:block">Status</span>
      </div>

      {!itens ? (
        <ul className="space-y-2 px-5 pb-5" aria-hidden>
          {Array.from({ length: 5 }, (_, i) => (
            <li key={i} className="h-9 animate-pulse rounded-md bg-white/5" />
          ))}
        </ul>
      ) : itens.length === 0 ? (
        <p className="px-5 pt-4 pb-8 text-center text-sm text-papel/70">
          Nenhuma data marcada nos próximos {DIAS_DO_PAINEL} dias. Céu de brigadeiro. ☀
        </p>
      ) : (
        <ol className="px-2 pb-2 [perspective:800px]">
          {itens.slice(0, LINHAS).map((item, i) => {
            const eHoje = item.data.startsWith(hoje ?? "");
            return (
              <li
                key={`${item.evento}-${item.processo_id}-${item.data}`}
                className="placa-letreiro"
                style={{ "--atraso": `${i * 70}ms` } as CSSProperties}
              >
                <Link
                  href={`/processos/${item.processo_id}`}
                  className={cn(
                    COLUNAS,
                    "rounded-lg px-3 py-2 font-mono text-sm uppercase transition-colors hover:bg-white/5 focus-visible:bg-white/10 focus-visible:outline-none",
                  )}
                >
                  <span
                    className={cn(
                      "flex items-center gap-1.5 text-xs whitespace-nowrap sm:text-sm",
                      eHoje ? "text-marca" : "text-papel/80",
                    )}
                  >
                    {eHoje && <span className="size-1.5 animate-pulse rounded-full bg-marca" aria-hidden />}
                    {rotuloDoDia(item.data.slice(0, 10), hoje ?? "")}
                  </span>
                  <span className="hidden font-bold text-marca sm:block">{EVENTOS[item.evento].curto}</span>
                  <span className="min-w-0">
                    <span className="block truncate font-sans font-semibold normal-case">{item.cliente}</span>
                    <span className="block text-[11px] text-papel/50 sm:hidden">
                      {EVENTOS[item.evento].rotulo}
                    </span>
                  </span>
                  <span className="hidden text-papel/70 sm:block">
                    {item.tipo}
                    {item.processo_id}
                  </span>
                  <span className="text-right font-bold sm:text-left">{item.consulado ?? "—"}</span>
                  <span className="hidden truncate text-xs text-papel/70 sm:block">
                    {rotuloSituacao(item.situacao)}
                  </span>
                </Link>
              </li>
            );
          })}
        </ol>
      )}

      {itens && (
        <footer className="flex items-center justify-between border-t border-white/10 px-5 py-3 text-xs text-papel/60">
          <span>
            {itens.length > LINHAS ? `Mostrando ${LINHAS} de ${itens.length}.` : "Todos os da semana."}
          </span>
          <Link
            href="/agenda"
            className="inline-flex items-center gap-1 font-semibold text-marca hover:underline focus-visible:underline focus-visible:outline-none"
          >
            Ver a agenda <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </footer>
      )}
    </section>
  );
}
