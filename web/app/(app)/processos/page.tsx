import { Plus } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { AreaProcessos } from "@/components/processos/area-processos";
import { BarraFiltros } from "@/components/processos/barra-filtros";
import { Paginacao } from "@/components/processos/paginacao";
import { Quadro, type Coluna } from "@/components/processos/quadro";
import { TabelaProcessos } from "@/components/processos/tabela";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet, apiLista } from "@/lib/api";
import { pode } from "@/lib/permissoes";
import { lerFiltros, paramsDoPainel, type Filtros } from "@/lib/processos";
import { usuarioAtual } from "@/lib/sessao";
import type { LinhaPainel, Referencias, Resumo, TipoProcesso } from "@/lib/tipos";

export const metadata: Metadata = { title: "Processos" };

const CARTOES_POR_COLUNA = 25;

export default function PaginaProcessos({ searchParams }: PageProps<"/processos">) {
  return (
    <div className="mx-auto max-w-[1400px]">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold">Processos</h1>
          <p className="mt-1 text-muted-foreground">Todos os embarques, do cadastro ao carimbo.</p>
        </div>
        <Suspense>
          <BotaoNovoProcesso />
        </Suspense>
      </header>
      {/* filtros vêm da URL (dado da requisição): tudo abaixo chega por streaming */}
      <Suspense fallback={<Esqueleto />}>
        <Conteudo searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

/** Só quem pode escrever vê o botão (a API recusaria de qualquer forma). */
async function BotaoNovoProcesso() {
  const usuario = await usuarioAtual();
  if (!pode(usuario.perfil, "escrever")) return null;
  return (
    <Button asChild className="h-11">
      <Link href="/processos/novo">
        <Plus className="size-4" /> Novo processo
      </Link>
    </Button>
  );
}

async function Conteudo({ searchParams }: { searchParams: PageProps<"/processos">["searchParams"] }) {
  const filtros = lerFiltros(await searchParams);
  const [usuario, referencias, resumo] = await Promise.all([
    usuarioAtual(),
    apiGet<Referencias>("/referencias"),
    apiGet<Resumo>("/painel/resumo"),
  ]);
  const situacoes = referencias.situacoes[filtros.tipo];
  const totais = Object.fromEntries(
    (Object.keys(resumo) as TipoProcesso[]).map((t) => [t, resumo[t].total]),
  ) as Record<TipoProcesso, number>;

  return (
    <AreaProcessos
      barra={
        <BarraFiltros
          filtros={filtros}
          situacoes={situacoes}
          consulados={referencias.consulados}
          totais={totais}
        />
      }
    >
      {filtros.visao === "quadro" ? (
        <Quadro
          colunas={await colunasDoQuadro(filtros, situacoes)}
          filtros={filtros}
          podeMover={pode(usuario.perfil, "escrever")}
        />
      ) : (
        <Tabela filtros={filtros} />
      )}
    </AreaProcessos>
  );
}

async function Tabela({ filtros }: { filtros: Filtros }) {
  const { itens, total } = await apiLista<LinhaPainel>("/painel", paramsDoPainel(filtros));
  return (
    <>
      <p className="mb-2 text-xs text-muted-foreground">
        Ordem: primeiro as datas marcadas mais próximas; depois os demais, dos mais novos aos mais antigos.
      </p>
      <TabelaProcessos linhas={itens} tipo={filtros.tipo} />
      <Paginacao filtros={filtros} total={total ?? itens.length} />
    </>
  );
}

/** Uma consulta por coluna, em paralelo (cada uma já traz o total da situação no X-Total-Count). */
async function colunasDoQuadro(filtros: Filtros, situacoes: string[]): Promise<Coluna[]> {
  return Promise.all(
    situacoes.map(async (situacao) => {
      const params = { ...paramsDoPainel({ ...filtros, situacao, pagina: 1 }, CARTOES_POR_COLUNA) };
      const { itens, total } = await apiLista<LinhaPainel>("/painel", params);
      return { situacao, itens, total: total ?? itens.length };
    }),
  );
}

function Esqueleto() {
  return (
    <div aria-hidden>
      <div className="mb-4 flex justify-between">
        <Skeleton className="h-11 w-96 rounded-xl" />
        <Skeleton className="h-11 w-48 rounded-xl" />
      </div>
      <Skeleton className="mb-6 h-[74px] w-full rounded-2xl" />
      <div className="space-y-2 rounded-2xl border bg-card p-4">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}
