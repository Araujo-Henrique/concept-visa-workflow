"use client";

import { CalendarCheck2, MapPin } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useMemo, useRef, useState, type KeyboardEvent } from "react";

import { SeloSituacao } from "@/components/processos/selos";
import {
  agruparPorDia,
  CABECALHO_DA_SEMANA,
  contarPorEvento,
  EVENTOS,
  ORDEM_DOS_EVENTOS,
  rotuloDoDia,
  tituloDoDia,
} from "@/lib/agenda";
import type { AgendaItem, EventoAgenda } from "@/lib/tipos";
import { cn } from "@/lib/utils";

type Props = {
  /** "AAAA-MM" */
  mes: string;
  /** "AAAA-MM-DD", no horário de Brasília (vem do servidor: o relógio do navegador pode estar errado) */
  hoje: string;
  /** dias da grade, de segunda a domingo */
  dias: string[];
  itens: AgendaItem[];
};

const MAX_LINHAS_NA_CELULA = 3;

/** Calendário do mês: um clique (ou as setas do teclado) no dia abre os compromissos dele ao lado. */
export function Calendario({ mes, hoje, dias, itens }: Props) {
  const [ocultos, setOcultos] = useState<Set<EventoAgenda>>(new Set());
  const visiveis = useMemo(() => itens.filter((i) => !ocultos.has(i.evento)), [itens, ocultos]);
  const porDia = useMemo(() => agruparPorDia(visiveis), [visiveis]);
  const contagemDoMes = useMemo(
    () => contarPorEvento(itens.filter((i) => i.data.startsWith(mes))),
    [itens, mes],
  );

  const [selecionado, setSelecionado] = useState(() => (hoje.startsWith(mes) ? hoje : `${mes}-01`));
  const celulas = useRef<(HTMLButtonElement | null)[]>([]);

  function alternar(evento: EventoAgenda) {
    setOcultos((atual) => {
      const novo = new Set(atual);
      if (novo.has(evento)) novo.delete(evento);
      else novo.add(evento);
      return novo;
    });
  }

  function mover(e: KeyboardEvent, indice: number) {
    const passo = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[e.key];
    let destino = passo === undefined ? undefined : indice + passo;
    if (e.key === "Home") destino = indice - (indice % 7);
    if (e.key === "End") destino = indice - (indice % 7) + 6;
    if (destino === undefined || destino < 0 || destino >= dias.length) return;
    e.preventDefault();
    setSelecionado(dias[destino]!);
    celulas.current[destino]?.focus();
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0">
        <fieldset className="mb-4 flex flex-wrap gap-2">
          <legend className="sr-only">Mostrar compromissos de</legend>
          {ORDEM_DOS_EVENTOS.map((evento) => {
            const ligado = !ocultos.has(evento);
            return (
              <button
                key={evento}
                type="button"
                aria-pressed={ligado}
                onClick={() => alternar(evento)}
                className={cn(
                  "inline-flex h-9 items-center gap-2 rounded-full border px-3 text-sm font-medium transition",
                  ligado ? "bg-card shadow-xs" : "border-dashed text-muted-foreground opacity-60",
                )}
              >
                <span className={cn("size-2.5 rounded-full", EVENTOS[evento].ponto)} aria-hidden />
                {EVENTOS[evento].rotulo}
                <span className="text-xs text-muted-foreground tabular-nums">
                  {contagemDoMes[evento] ?? 0}
                </span>
              </button>
            );
          })}
        </fieldset>

        <div className="overflow-hidden rounded-2xl border bg-card shadow-sm">
          <div className="grid grid-cols-7 border-b bg-tinta text-papel dark:bg-muted" aria-hidden>
            {CABECALHO_DA_SEMANA.map((d) => (
              <span
                key={d}
                className="py-2 text-center font-heading text-[11px] font-bold tracking-[0.2em] uppercase"
              >
                {d}
              </span>
            ))}
          </div>
          <div className="grid grid-cols-7" role="group" aria-label="Dias do mês">
            {dias.map((dia, i) => {
              const doDia = porDia.get(dia) ?? [];
              const contagem = contarPorEvento(doDia);
              const tipos = ORDEM_DOS_EVENTOS.filter((e) => contagem[e]);
              const foraDoMes = !dia.startsWith(mes);
              const eHoje = dia === hoje;
              const eSelecionado = dia === selecionado;
              return (
                <button
                  key={dia}
                  ref={(el) => {
                    celulas.current[i] = el;
                  }}
                  type="button"
                  tabIndex={eSelecionado ? 0 : -1}
                  aria-pressed={eSelecionado}
                  aria-label={`${tituloDoDia(dia)}: ${doDia.length ? `${doDia.length} compromisso${doDia.length > 1 ? "s" : ""}` : "nenhum compromisso"}`}
                  onClick={() => setSelecionado(dia)}
                  onKeyDown={(e) => mover(e, i)}
                  className={cn(
                    "relative flex min-h-16 flex-col items-stretch gap-1 border-r border-b p-1.5 text-left outline-none sm:min-h-28 sm:p-2",
                    "transition-colors hover:bg-muted/60 focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-ring",
                    i % 7 === 6 && "border-r-0",
                    i >= dias.length - 7 && "border-b-0",
                    foraDoMes && "bg-muted/30 text-muted-foreground",
                  )}
                >
                  {eSelecionado && (
                    <motion.span
                      layoutId="dia-selecionado"
                      className="absolute inset-0.5 rounded-lg bg-marca-suave ring-1 ring-marca/40"
                      transition={{ type: "spring", stiffness: 500, damping: 40 }}
                      aria-hidden
                    />
                  )}
                  <span
                    className={cn(
                      "relative grid size-7 place-items-center rounded-full text-sm font-semibold tabular-nums",
                      eHoje && "bg-primary text-primary-foreground",
                    )}
                  >
                    {Number(dia.slice(8))}
                  </span>
                  {/* celular: só os pontos; telas maiores: quantos de cada tipo */}
                  <span className="relative flex flex-wrap gap-1 sm:hidden" aria-hidden>
                    {tipos.map((e) => (
                      <span key={e} className={cn("size-1.5 rounded-full", EVENTOS[e].ponto)} />
                    ))}
                  </span>
                  <span className="relative hidden space-y-0.5 sm:block" aria-hidden>
                    {tipos.slice(0, MAX_LINHAS_NA_CELULA).map((e) => (
                      <span
                        key={e}
                        className={cn(
                          "flex items-center justify-between gap-1 truncate rounded px-1.5 py-px text-[11px] font-semibold",
                          EVENTOS[e].chip,
                        )}
                      >
                        <span className="truncate">{EVENTOS[e].rotulo}</span>
                        <span className="tabular-nums">{contagem[e]}</span>
                      </span>
                    ))}
                    {tipos.length > MAX_LINHAS_NA_CELULA && (
                      <span className="block px-1.5 text-[11px] text-muted-foreground">
                        +{tipos.length - MAX_LINHAS_NA_CELULA} tipos
                      </span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <PainelDoDia dia={selecionado} hoje={hoje} itens={porDia.get(selecionado) ?? []} />
    </div>
  );
}

function PainelDoDia({ dia, hoje, itens }: { dia: string; hoje: string; itens: AgendaItem[] }) {
  const relativo = rotuloDoDia(dia, hoje);
  return (
    <aside
      className="self-start overflow-hidden rounded-2xl border bg-card shadow-sm xl:sticky xl:top-6"
      aria-live="polite"
      aria-label="Compromissos do dia"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={dia}
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -16 }}
          transition={{ duration: 0.18 }}
        >
          <header className="border-b px-5 py-4">
            <p className="text-xs font-semibold tracking-widest text-marca-forte uppercase">
              {["Hoje", "Amanhã", "Ontem"].includes(relativo) ? relativo : "Dia"}
            </p>
            <h2 className="mt-0.5 text-lg font-bold first-letter:uppercase">{tituloDoDia(dia)}</h2>
            <p className="text-sm text-muted-foreground">
              {itens.length === 0
                ? "Nenhum compromisso."
                : `${itens.length} compromisso${itens.length > 1 ? "s" : ""}`}
            </p>
          </header>

          {itens.length === 0 ? (
            <div className="grid place-items-center gap-2 px-5 py-10 text-center text-sm text-muted-foreground">
              <CalendarCheck2 className="size-8 text-marca" aria-hidden />
              Dia livre de embarques.
            </div>
          ) : (
            <ol className="max-h-[70vh] divide-y overflow-y-auto">
              {itens.map((item) => (
                <li key={`${item.evento}-${item.processo_id}`}>
                  <Link
                    href={`/processos/${item.processo_id}`}
                    className="block px-5 py-3 transition-colors hover:bg-muted/60 focus-visible:bg-muted/60 focus-visible:outline-none"
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[11px] font-bold tracking-wide",
                          EVENTOS[item.evento].chip,
                        )}
                      >
                        {EVENTOS[item.evento].rotulo}
                      </span>
                      <span className="font-mono text-xs text-muted-foreground">
                        {item.tipo} · #{item.processo_id}
                      </span>
                    </span>
                    <span className="mt-1.5 block truncate font-semibold">{item.cliente}</span>
                    <span className="mt-1 flex items-center justify-between gap-2">
                      <SeloSituacao situacao={item.situacao} />
                      {item.consulado && (
                        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                          <MapPin className="size-3" aria-hidden />
                          {item.consulado}
                        </span>
                      )}
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          )}
        </motion.div>
      </AnimatePresence>
    </aside>
  );
}
