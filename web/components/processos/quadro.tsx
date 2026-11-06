"use client";

import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  pointerWithin,
  rectIntersection,
  type CollisionDetection,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { GripVertical, Users } from "lucide-react";
import Link from "next/link";
import { useId, useOptimistic, useState, useTransition } from "react";
import { toast } from "sonner";

import { mudarSituacao } from "@/app/acoes/processos";
import { DialogoMotivo } from "@/components/processos/dialogo-motivo";
import { SeloResultado, SeloSituacao } from "@/components/processos/selos";
import { rotuloSituacao } from "@/lib/formatos";
import { datasPrincipais, formatarDataCurta, urlDosFiltros, type Filtros } from "@/lib/processos";
import type { LinhaPainel } from "@/lib/tipos";
import { cn } from "@/lib/utils";

export type Coluna = { situacao: string; itens: LinhaPainel[]; total: number };

/**
 * Destino = coluna sob o ponteiro (as faixas vazias são estreitas: pela área do card, a coluna vizinha
 * "ganharia"). Sem ponteiro (arrasto pelo teclado), vale a área.
 */
const colisao: CollisionDetection = (args) => {
  const sobOPonteiro = pointerWithin(args);
  return sobOPonteiro.length ? sobOPonteiro : rectIntersection(args);
};
type Movimento = { processo: LinhaPainel; de: string; para: string };

/** Aplica um movimento às colunas (usado na atualização otimista: o card muda de coluna na hora). */
export function moverCartao(colunas: Coluna[], { processo, de, para }: Movimento): Coluna[] {
  return colunas.map((c) => {
    if (c.situacao === de)
      return {
        ...c,
        itens: c.itens.filter((i) => i.processo_id !== processo.processo_id),
        total: c.total - 1,
      };
    if (c.situacao === para)
      return { ...c, itens: [{ ...processo, situacao: para }, ...c.itens], total: c.total + 1 };
    return c;
  });
}

/**
 * Quadro (kanban): uma coluna por situação. Arrastar um card muda a situação de verdade (gera o evento no
 * histórico). Funciona também pelo teclado: Tab até o card, espaço para pegar, setas para mover, espaço para soltar.
 */
export function Quadro({
  colunas,
  filtros,
  podeMover,
}: {
  colunas: Coluna[];
  filtros: Filtros;
  podeMover: boolean;
}) {
  const idQuadro = useId();
  const [otimistas, mover] = useOptimistic(colunas, moverCartao);
  const [, iniciar] = useTransition();
  const [arrastando, setArrastando] = useState<LinhaPainel | null>(null);
  const [reabrir, setReabrir] = useState<Movimento | null>(null);

  const sensores = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), // clique curto abre o processo
    useSensor(KeyboardSensor),
  );

  function executar(movimento: Movimento, motivo?: string) {
    iniciar(async () => {
      mover(movimento);
      const r = await mudarSituacao(movimento.processo.processo_id, movimento.para, motivo);
      if (r.ok) {
        toast.success(`#${movimento.processo.processo_id} carimbado`, {
          description: `${rotuloSituacao(movimento.de)} → ${rotuloSituacao(movimento.para)}`,
        });
      } else {
        toast.error("Não deu para mudar a situação", { description: r.erro }); // o card volta sozinho
      }
    });
  }

  function aoSoltar({ active, over }: DragEndEvent) {
    setArrastando(null);
    const processo = active.data.current?.processo as LinhaPainel | undefined;
    const para = over?.id as string | undefined;
    if (!processo || !para || para === processo.situacao) return;
    const movimento = { processo, de: processo.situacao, para };
    if (processo.situacao === "Concluido")
      setReabrir(movimento); // reabrir exige motivo
    else executar(movimento);
  }

  return (
    <>
      <DndContext
        id={idQuadro} // id fixo: sem ele, os ids de acessibilidade mudam entre servidor e navegador
        sensors={sensores}
        collisionDetection={colisao}
        onDragStart={({ active }: DragStartEvent) =>
          setArrastando((active.data.current?.processo as LinhaPainel) ?? null)
        }
        onDragEnd={aoSoltar}
        onDragCancel={() => setArrastando(null)}
        accessibility={{
          announcements: {
            onDragStart: ({ active }) => `Pegou o processo ${active.id}.`,
            onDragOver: ({ over }) =>
              over ? `Sobre ${rotuloSituacao(String(over.id))}.` : "Fora das colunas.",
            onDragEnd: ({ active, over }) =>
              over ? `Processo ${active.id} solto em ${rotuloSituacao(String(over.id))}.` : "Cancelado.",
            onDragCancel: () => "Cancelado.",
          },
        }}
      >
        <div className="-mx-4 overflow-x-auto px-4 pb-4 sm:-mx-8 sm:px-8 lg:-mx-10 lg:px-10">
          <div className="flex items-start gap-3">
            {otimistas.map((coluna) => (
              <ColunaQuadro
                key={coluna.situacao}
                coluna={coluna}
                filtros={filtros}
                podeMover={podeMover}
                recolhida={coluna.total === 0}
              />
            ))}
          </div>
        </div>
        <DragOverlay dropAnimation={{ duration: 180 }}>
          {arrastando && <Cartao processo={arrastando} levantado />}
        </DragOverlay>
      </DndContext>

      <DialogoMotivo
        aberto={reabrir !== null}
        destino={reabrir?.para ?? null}
        aoCancelar={() => setReabrir(null)}
        aoConfirmar={(motivo) => {
          if (reabrir) executar(reabrir, motivo);
          setReabrir(null);
        }}
      />
    </>
  );
}

function ColunaQuadro({
  coluna,
  filtros,
  podeMover,
  recolhida,
}: {
  coluna: Coluna;
  filtros: Filtros;
  podeMover: boolean;
  /**
   * Coluna vazia vira uma faixa estreita da altura do quadro, para as colunas com processos caberem na tela.
   * Continua recebendo cards (acende quando um passa por cima) e não muda de largura no meio do arrasto.
   */
  recolhida: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: coluna.situacao, disabled: !podeMover });
  const restantes = coluna.total - coluna.itens.length;

  if (recolhida)
    return (
      <section
        ref={setNodeRef}
        aria-label={`${rotuloSituacao(coluna.situacao)}: nenhum processo`}
        className={cn(
          "flex min-h-56 w-11 shrink-0 flex-col items-center gap-3 self-stretch rounded-2xl border border-dashed bg-muted/30 py-3 transition-colors",
          isOver && "border-marca bg-marca-suave text-foreground",
        )}
      >
        <span className="text-xs font-semibold text-muted-foreground tabular-nums">0</span>
        <span className="text-xs font-medium whitespace-nowrap text-muted-foreground [writing-mode:vertical-rl]">
          {rotuloSituacao(coluna.situacao)}
        </span>
      </section>
    );

  return (
    <section
      ref={setNodeRef}
      aria-label={`${rotuloSituacao(coluna.situacao)}: ${coluna.total} processos`}
      className={cn(
        "flex w-72 shrink-0 flex-col rounded-2xl border bg-muted/50 transition-colors",
        isOver && "border-marca bg-marca-suave/60",
      )}
    >
      <header className="flex items-center justify-between px-3 pt-3 pb-2">
        <SeloSituacao situacao={coluna.situacao} />
        <span className="text-xs font-semibold tabular-nums text-muted-foreground">
          {coluna.total.toLocaleString("pt-BR")}
        </span>
      </header>
      <div className="flex max-h-[calc(100dvh-20rem)] min-h-32 flex-col gap-2 overflow-y-auto px-2 pb-2">
        {coluna.itens.map((p) => (
          <CartaoArrastavel key={p.processo_id} processo={p} podeMover={podeMover} />
        ))}
        {coluna.itens.length === 0 && (
          <p className="grid flex-1 place-items-center rounded-xl border border-dashed py-6 text-xs text-muted-foreground">
            {podeMover ? "Solte um processo aqui" : "Vazio"}
          </p>
        )}
        {restantes > 0 && (
          <Link
            href={urlDosFiltros({ ...filtros, visao: "tabela", situacao: coluna.situacao, pagina: 1 })}
            className="rounded-lg px-2 py-2 text-center text-xs font-medium text-marca-forte hover:bg-card"
          >
            e mais {restantes.toLocaleString("pt-BR")} · ver na tabela
          </Link>
        )}
      </div>
    </section>
  );
}

function CartaoArrastavel({ processo, podeMover }: { processo: LinhaPainel; podeMover: boolean }) {
  const { setNodeRef, attributes, listeners, isDragging } = useDraggable({
    id: processo.processo_id,
    data: { processo },
    disabled: !podeMover,
  });
  return (
    <div ref={setNodeRef} className={cn(isDragging && "opacity-30")}>
      <Cartao
        processo={processo}
        alca={
          podeMover
            ? { ...attributes, ...listeners, "aria-label": `Mover o processo ${processo.processo_id}` }
            : undefined
        }
      />
    </div>
  );
}

/** Mini cartão de embarque: número + consulado no topo, cliente, pessoas, data principal e resultado. */
function Cartao({
  processo,
  alca,
  levantado = false,
}: {
  processo: LinhaPainel;
  alca?: Record<string, unknown>;
  levantado?: boolean;
}) {
  const data = datasPrincipais(processo).find((d) => d.valor);
  return (
    <article
      className={cn(
        "relative overflow-hidden rounded-xl border bg-card shadow-xs transition-shadow hover:shadow-md",
        levantado && "rotate-2 shadow-xl ring-2 ring-marca",
      )}
    >
      <div className="flex items-center gap-2 bg-tinta px-3 py-1.5 text-papel">
        <span className="font-heading text-[11px] font-bold tracking-widest">#{processo.processo_id}</span>
        {"consulado" in processo && processo.consulado && (
          <span className="font-heading text-[10px] font-bold tracking-widest text-marca">
            {processo.consulado}
          </span>
        )}
        {alca && (
          <button
            type="button"
            {...alca}
            className="ml-auto -mr-1 cursor-grab rounded p-0.5 text-papel/60 hover:text-papel active:cursor-grabbing"
          >
            <GripVertical className="size-4" />
          </button>
        )}
      </div>
      <div className="space-y-2 p-3">
        <Link
          href={`/processos/${processo.processo_id}`}
          className="line-clamp-2 text-sm font-semibold leading-snug outline-none after:absolute after:inset-0 after:top-8 focus-visible:underline"
        >
          {processo.cliente}
        </Link>
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Users className="size-3" /> {processo.n_solicitantes}
          </span>
          {data && (
            <span className="tabular-nums">
              {data.rotulo} {formatarDataCurta(data.valor)}
            </span>
          )}
        </div>
        <SeloResultado resultado={processo.resultado_geral} />
      </div>
    </article>
  );
}
