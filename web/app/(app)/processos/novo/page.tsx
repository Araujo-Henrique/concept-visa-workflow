import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Assistente } from "@/components/processos/assistente";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet } from "@/lib/api";
import { ErroApi } from "@/lib/erros";
import type { Cliente, Referencias } from "@/lib/tipos";

export const metadata: Metadata = { title: "Novo processo" };

export default function PaginaNovoProcesso({ searchParams }: PageProps<"/processos/novo">) {
  return (
    <div className="mx-auto max-w-5xl">
      <Link
        href="/processos"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Processos
      </Link>
      <header className="mt-3 mb-8">
        <h1 className="text-3xl font-extrabold">Novo processo</h1>
        <p className="mt-1 text-muted-foreground">Check-in em cinco paradas. No fim, o cartão de embarque.</p>
      </header>
      <Suspense fallback={<Skeleton className="mx-auto h-[420px] max-w-3xl rounded-2xl" />}>
        <Conteudo searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Conteudo({ searchParams }: { searchParams: PageProps<"/processos/novo">["searchParams"] }) {
  const { cliente } = await searchParams;
  const id = Number(cliente);
  const [referencias, clienteInicial] = await Promise.all([
    apiGet<Referencias>("/referencias"),
    // vindo da ficha do cliente (?cliente=12), o assistente já começa com ele escolhido
    Number.isInteger(id) && id > 0
      ? apiGet<Cliente>(`/clientes/${id}`).catch((erro) => {
          if (erro instanceof ErroApi && erro.status === 404) return null;
          throw erro;
        })
      : Promise.resolve(null),
  ]);
  return <Assistente referencias={referencias} clienteInicial={clienteInicial} />;
}
