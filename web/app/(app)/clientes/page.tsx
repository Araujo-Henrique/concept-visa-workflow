import { Mail, Phone } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { BuscaClientes, NovoCliente, PaginacaoClientes } from "@/components/clientes/controles";
import { Skeleton } from "@/components/ui/skeleton";
import { apiLista } from "@/lib/api";
import { formatarTelefone } from "@/lib/formularios";
import { pode } from "@/lib/permissoes";
import { usuarioAtual } from "@/lib/sessao";
import type { ClienteLista } from "@/lib/tipos";

export const metadata: Metadata = { title: "Clientes" };

const POR_PAGINA = 50;

export default function PaginaClientes({ searchParams }: PageProps<"/clientes">) {
  return (
    <div className="mx-auto max-w-6xl">
      <header className="mb-6">
        <h1 className="text-3xl font-extrabold">Clientes</h1>
        <p className="mt-1 text-muted-foreground">Quem viaja com a Concept, e cada viagem de cada um.</p>
      </header>
      <Suspense fallback={<Esqueleto />}>
        <Conteudo searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Conteudo({ searchParams }: { searchParams: PageProps<"/clientes">["searchParams"] }) {
  const busca = await searchParams;
  const termo = typeof busca.busca === "string" ? busca.busca : "";
  const pagina = Math.max(1, Number(busca.pagina) || 1);
  const [usuario, { itens, total }] = await Promise.all([
    usuarioAtual(),
    apiLista<ClienteLista>("/clientes", {
      busca: termo,
      limit: POR_PAGINA,
      offset: (pagina - 1) * POR_PAGINA,
    }),
  ]);

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <BuscaClientes inicial={termo} />
        {pode(usuario.perfil, "escrever") && (
          <div className="ml-auto">
            <NovoCliente />
          </div>
        )}
      </div>

      {itens.length === 0 ? (
        <div className="grid place-items-center rounded-2xl border border-dashed bg-card px-6 py-16 text-center">
          <p className="font-heading text-lg font-bold">Nenhum cliente encontrado</p>
          <p className="mt-1 text-sm text-muted-foreground">Confira a busca ou cadastre um cliente novo.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border bg-card">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b text-left text-xs tracking-wide text-muted-foreground uppercase">
                <th className="px-4 py-3 font-medium">Cliente</th>
                <th className="px-4 py-3 font-medium">Contato</th>
                <th className="px-4 py-3 font-medium">Grupo</th>
                <th className="px-4 py-3 text-right font-medium">Processos</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((c) => (
                <tr
                  key={c.id}
                  className="relative border-b transition-colors last:border-0 hover:bg-marca-suave/50"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/clientes/${c.id}`}
                      className="font-medium outline-none after:absolute after:inset-0 focus-visible:after:ring-2 focus-visible:after:ring-ring focus-visible:after:ring-inset"
                    >
                      {c.nome}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {c.telefone && (
                      <span className="flex items-center gap-1.5 tabular-nums">
                        <Phone className="size-3.5" /> {formatarTelefone(c.telefone)}
                      </span>
                    )}
                    {c.email && (
                      <span className="flex items-center gap-1.5 truncate">
                        <Mail className="size-3.5" /> {c.email}
                      </span>
                    )}
                    {!c.telefone && !c.email && "—"}
                  </td>
                  <td className="px-4 py-3">{c.grupo ?? <span className="text-muted-foreground">—</span>}</td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums">{c.n_processos}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <PaginacaoClientes pagina={pagina} total={total ?? itens.length} porPagina={POR_PAGINA} busca={termo} />
    </>
  );
}

function Esqueleto() {
  return (
    <div aria-hidden>
      <Skeleton className="mb-6 h-11 w-96 rounded-xl" />
      <div className="space-y-2 rounded-2xl border bg-card p-4">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}
