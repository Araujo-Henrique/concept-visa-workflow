import { ArrowLeft, Users } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { VistaProcesso } from "@/components/passaporte/vista-processo";
import { SeloResultado, SeloSituacao } from "@/components/processos/selos";
import { Skeleton } from "@/components/ui/skeleton";
import { hojeEmSP } from "@/lib/agenda";
import { apiGet, apiLista } from "@/lib/api";
import { TIPOS } from "@/lib/formatos";
import { pode } from "@/lib/permissoes";
import { urlDosFiltros } from "@/lib/processos";
import { usuarioAtual } from "@/lib/sessao";
import type { Evento, LinhaPainel, ProcessoDetalhe, Referencias, TipoProcesso } from "@/lib/tipos";

export const metadata: Metadata = { title: "Processo" };

const ROTA_DO_TIPO: Record<TipoProcesso, string> = {
  OBT: "/processos-obt",
  REN: "/processos-ren",
  PASS: "/processos-pass",
};

export default function PaginaProcesso({ params }: PageProps<"/processos/[id]">) {
  return (
    <div className="mx-auto max-w-6xl">
      <Suspense fallback={<Esqueleto />}>
        <Conteudo params={params} />
      </Suspense>
    </div>
  );
}

async function Conteudo({ params }: { params: PageProps<"/processos/[id]">["params"] }) {
  const id = Number((await params).id);
  if (!Number.isInteger(id) || id <= 0) notFound();

  // o painel diz o tipo (e traz cliente, telefone, quem orientou...); com o tipo, buscamos o resto
  const { itens } = await apiLista<LinhaPainel>("/painel", { processo_id: id, limit: 1 });
  const linha = itens[0];
  if (!linha) notFound();

  const [detalhe, eventos, referencias, usuario] = await Promise.all([
    apiGet<ProcessoDetalhe>(`${ROTA_DO_TIPO[linha.tipo]}/${id}`),
    apiGet<Evento[]>(`/processos/${id}/eventos`),
    apiGet<Referencias>("/referencias"),
    usuarioAtual(),
  ]);

  return (
    <>
      <header className="mb-8">
        <Link
          href={urlDosFiltros({ tipo: linha.tipo })}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Processos · {TIPOS[linha.tipo].nome}
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
          <h1 className="text-3xl font-extrabold">{linha.cliente}</h1>
          <span className="font-heading text-sm font-bold tracking-widest text-muted-foreground">
            #{linha.processo_id}
          </span>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <SeloSituacao situacao={linha.situacao} />
          <SeloResultado resultado={linha.resultado_geral} />
          <span className="flex items-center gap-1 text-muted-foreground">
            <Users className="size-4" />{" "}
            {linha.n_solicitantes > 1 ? `${linha.n_solicitantes} pessoas: ${linha.solicitantes}` : "1 pessoa"}
          </span>
        </div>
      </header>

      <VistaProcesso
        hoje={hojeEmSP()}
        linha={linha}
        detalhe={detalhe}
        eventos={eventos}
        referencias={referencias}
        permissoes={{ escrever: pode(usuario.perfil, "escrever"), apagar: pode(usuario.perfil, "apagar") }}
      />
    </>
  );
}

function Esqueleto() {
  return (
    <div aria-hidden>
      <Skeleton className="h-4 w-48" />
      <Skeleton className="mt-4 h-9 w-80" />
      <Skeleton className="mt-3 mb-8 h-6 w-64" />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
        <Skeleton className="h-[560px] rounded-2xl" />
        <Skeleton className="h-[420px] rounded-2xl" />
      </div>
    </div>
  );
}
