import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { Calendario } from "@/components/agenda/calendario";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet } from "@/lib/api";
import { gradeDoMes, hojeEmSP, lerMes, mesVizinho, nomeDoMes, urlDaAgenda } from "@/lib/agenda";
import type { AgendaItem } from "@/lib/tipos";

export const metadata: Metadata = { title: "Agenda" };

/** Agenda do mês: orientações, CASV, entrevistas, despachos e Polícia Federal de todos os processos. */
export default function PaginaAgenda({ searchParams }: PageProps<"/agenda">) {
  return (
    <div className="mx-auto max-w-[1400px]">
      <Suspense fallback={<Esqueleto />}>
        <Conteudo searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Conteudo({ searchParams }: { searchParams: PageProps<"/agenda">["searchParams"] }) {
  const busca = await searchParams;
  await connection(); // "hoje" é da hora do pedido, não do build
  const hoje = hojeEmSP();
  const mes = lerMes(busca.mes, hoje);
  const dias = gradeDoMes(mes);
  const itens = await apiGet<AgendaItem[]>("/painel/agenda", { de: dias[0], ate: dias[dias.length - 1] });

  return (
    <>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold">Agenda</h1>
          <p className="mt-1 text-muted-foreground">Cada data marcada dos processos, dia a dia.</p>
        </div>
        <nav className="flex items-center gap-2" aria-label="Meses">
          <Button asChild variant="outline" size="icon-lg">
            <Link href={urlDaAgenda(mesVizinho(mes, -1), hoje)} aria-label="Mês anterior">
              <ChevronLeft className="size-4" />
            </Link>
          </Button>
          <h2 className="min-w-48 text-center text-lg font-bold first-letter:uppercase" aria-live="polite">
            {nomeDoMes(mes)}
          </h2>
          <Button asChild variant="outline" size="icon-lg">
            <Link href={urlDaAgenda(mesVizinho(mes, 1), hoje)} aria-label="Próximo mês">
              <ChevronRight className="size-4" />
            </Link>
          </Button>
          {mes !== hoje.slice(0, 7) && (
            <Button asChild variant="secondary" size="lg">
              <Link href="/agenda">Hoje</Link>
            </Button>
          )}
        </nav>
      </header>
      {/* key: trocar de mês recomeça a seleção do dia */}
      <Calendario key={mes} mes={mes} hoje={hoje} dias={dias} itens={itens} />
    </>
  );
}

function Esqueleto() {
  return (
    <div aria-hidden>
      <div className="mb-6 flex justify-between">
        <Skeleton className="h-16 w-64" />
        <Skeleton className="h-9 w-72" />
      </div>
      <Skeleton className="mb-4 h-9 w-full max-w-3xl rounded-full" />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Skeleton className="h-[640px] rounded-2xl" />
        <Skeleton className="h-80 rounded-2xl" />
      </div>
    </div>
  );
}
