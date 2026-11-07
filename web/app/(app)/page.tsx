import { Plane } from "lucide-react";
import { connection } from "next/server";
import { Suspense, type ReactNode } from "react";

import { DIAS_DO_PAINEL, PainelEmbarque } from "@/components/inicio/painel-embarque";
import { Contador } from "@/components/movimento/contador";
import { Skeleton } from "@/components/ui/skeleton";
import { hojeEmSP, somarDias } from "@/lib/agenda";
import { apiGet } from "@/lib/api";
import { emAndamento, rotuloSituacao, saudacao, situacoesAbertas, TIPOS } from "@/lib/formatos";
import { usuarioAtual } from "@/lib/sessao";
import type { AgendaItem, Resumo, ResumoTipo, TipoProcesso } from "@/lib/tipos";

const ORDEM = Object.keys(TIPOS) as TipoProcesso[];

/**
 * Início: um "cartão de embarque" por tipo de processo, com o que está em andamento, e o painel de embarque
 * com as datas marcadas dos próximos dias.
 * Navegação instantânea: a moldura aparece na hora e cada parte que depende da API chega por streaming,
 * dentro do seu próprio <Suspense> (dado de trabalho não é cacheado: os números são sempre os atuais).
 */
export default function Inicio() {
  return (
    <div className="mx-auto max-w-6xl">
      <header className="mb-10">
        <Suspense fallback={<SaudacaoEsqueleto />}>
          <Saudacao />
        </Suspense>
        <p className="mt-2 text-muted-foreground">Veja como estão os embarques de hoje.</p>
      </header>

      <section className="grid gap-5 md:grid-cols-3" aria-label="Processos por tipo">
        <Suspense
          fallback={ORDEM.map((tipo) => (
            <Cartao key={tipo} tipo={tipo} />
          ))}
        >
          <Cartoes />
        </Suspense>
      </section>

      <div className="mt-8">
        <Suspense fallback={<PainelEmbarque />}>
          <Embarques />
        </Suspense>
      </div>
    </div>
  );
}

async function Embarques() {
  await connection(); // "hoje" é da hora do pedido, não do build
  const hoje = hojeEmSP();
  const itens = await apiGet<AgendaItem[]>("/painel/agenda", {
    de: hoje,
    ate: somarDias(hoje, DIAS_DO_PAINEL - 1),
  });
  return <PainelEmbarque itens={itens} hoje={hoje} />;
}

async function Saudacao() {
  const usuario = await usuarioAtual();
  return (
    <>
      <p className="text-sm font-medium text-marca-forte">
        {new Intl.DateTimeFormat("pt-BR", { dateStyle: "full", timeZone: "America/Sao_Paulo" }).format(
          new Date(),
        )}
      </p>
      <h1 className="mt-1 text-3xl font-extrabold sm:text-4xl">
        {saudacao()}, {usuario.nome.split(" ")[0]}.
      </h1>
    </>
  );
}

function SaudacaoEsqueleto() {
  return (
    <div aria-hidden>
      <Skeleton className="h-4 w-56" />
      <Skeleton className="mt-3 h-9 w-72" />
    </div>
  );
}

async function Cartoes() {
  const resumo = await apiGet<Resumo>("/painel/resumo");
  return ORDEM.map((tipo) => <Cartao key={tipo} tipo={tipo} dados={resumo[tipo]} />);
}

/** Cartão de embarque. Sem `dados`, é o esqueleto: a moldura já aparece, os números chegam depois. */
function Cartao({ tipo, dados }: { tipo: TipoProcesso; dados?: ResumoTipo }) {
  const situacoes = dados ? situacoesAbertas(dados.por_situacao).slice(0, 4) : [];
  return (
    <article className="overflow-hidden rounded-2xl border bg-card shadow-sm" aria-busy={!dados}>
      <div className="flex items-center justify-between bg-tinta px-5 py-3 text-papel">
        <span className="font-heading text-xs font-bold tracking-[0.25em]">{tipo}</span>
        <Plane className="size-4 text-marca" aria-hidden />
        <span className="text-xs text-papel/70">{TIPOS[tipo].nome}</span>
      </div>

      <div className="px-5 pt-5 pb-4">
        <p className="text-sm text-muted-foreground">Em andamento</p>
        {dados ? (
          <>
            <Contador
              valor={emAndamento(dados.por_situacao)}
              className="font-heading text-5xl font-extrabold text-marca-forte"
            />
            <p className="mt-1 text-sm text-muted-foreground">
              de <Contador valor={dados.total} className="font-semibold text-foreground" /> no total
            </p>
          </>
        ) : (
          <>
            <Skeleton className="mt-2 h-12 w-24" />
            <Skeleton className="mt-2 h-4 w-28" />
          </>
        )}
      </div>

      {/* picote do cartão de embarque */}
      <div className="relative mx-5 border-t-2 border-dashed" aria-hidden>
        <span className="absolute -top-3 -left-8 size-6 rounded-full bg-background" />
        <span className="absolute -top-3 -right-8 size-6 rounded-full bg-background" />
      </div>

      <ul className="space-y-2 px-5 py-4 text-sm">
        {!dados && <LinhasEsqueleto />}
        {dados && situacoes.length === 0 && (
          <li className="text-muted-foreground">Tudo concluído por aqui. ✓</li>
        )}
        {situacoes.map(([situacao, n]) => (
          <li key={situacao} className="flex items-center justify-between">
            <span>{rotuloSituacao(situacao)}</span>
            <span className="rounded-full bg-marca-suave px-2.5 py-0.5 font-semibold text-accent-foreground tabular-nums">
              {n}
            </span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function LinhasEsqueleto(): ReactNode {
  return [0, 1, 2].map((i) => (
    <li key={i} className="flex items-center justify-between" aria-hidden>
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-5 w-10 rounded-full" />
    </li>
  ));
}
