import { ArrowLeft, Mail, MessageCircle, Phone, Plane, Plus, Users } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { EsqueletoHistorico, HistoricoAlteracoes } from "@/components/auditoria/historico-alteracoes";
import { EditarCliente, ExcluirCliente } from "@/components/clientes/controles";
import { SeloResultado, SeloSituacao } from "@/components/processos/selos";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet, apiLista } from "@/lib/api";
import { ErroApi } from "@/lib/erros";
import { TIPOS } from "@/lib/formatos";
import { formatarTelefone, linkWhatsapp } from "@/lib/formularios";
import { pode } from "@/lib/permissoes";
import { datasPrincipais, formatarData } from "@/lib/processos";
import { usuarioAtual } from "@/lib/sessao";
import type { Cliente, LinhaPainel } from "@/lib/tipos";

export const metadata: Metadata = { title: "Cliente" };

export default function PaginaCliente({ params }: PageProps<"/clientes/[id]">) {
  return (
    <div className="mx-auto max-w-5xl">
      <Suspense fallback={<Esqueleto />}>
        <Conteudo params={params} />
      </Suspense>
    </div>
  );
}

async function buscarCliente(id: number): Promise<Cliente> {
  try {
    return await apiGet<Cliente>(`/clientes/${id}`);
  } catch (erro) {
    if (erro instanceof ErroApi && erro.status === 404) notFound();
    throw erro;
  }
}

async function Conteudo({ params }: { params: PageProps<"/clientes/[id]">["params"] }) {
  const id = Number((await params).id);
  if (!Number.isInteger(id) || id <= 0) notFound();
  const [cliente, { itens: processos }, usuario] = await Promise.all([
    buscarCliente(id),
    apiLista<LinhaPainel>("/painel", { cliente_id: id, limit: 200 }),
    usuarioAtual(),
  ]);
  const escreve = pode(usuario.perfil, "escrever");
  const apaga = pode(usuario.perfil, "apagar_cliente"); // admin e atendente (o admin restaura)
  const whatsapp = linkWhatsapp(cliente.telefone);

  return (
    <>
      <Link
        href="/clientes"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Clientes
      </Link>

      <header className="mt-3 mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold">{cliente.nome}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
            {cliente.telefone && (
              <span className="flex items-center gap-1.5 tabular-nums">
                <Phone className="size-4" /> {formatarTelefone(cliente.telefone)}
              </span>
            )}
            {whatsapp && (
              <a
                href={whatsapp}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 font-medium text-marca-forte hover:underline"
              >
                <MessageCircle className="size-4" /> WhatsApp
              </a>
            )}
            {cliente.email && (
              <a href={`mailto:${cliente.email}`} className="flex items-center gap-1.5 hover:text-foreground">
                <Mail className="size-4" /> {cliente.email}
              </a>
            )}
            {cliente.grupo && (
              <span className="flex items-center gap-1.5">
                <Users className="size-4" /> {cliente.grupo}
              </span>
            )}
          </div>
        </div>
        {(escreve || apaga) && (
          <div className="flex flex-wrap gap-2">
            {apaga && <ExcluirCliente cliente={cliente} processos={processos.length} />}
            {escreve && (
              <>
                <EditarCliente cliente={cliente} />
                <Button asChild>
                  <Link href={`/processos/novo?cliente=${cliente.id}`}>
                    <Plus className="size-4" /> Novo processo
                  </Link>
                </Button>
              </>
            )}
          </div>
        )}
      </header>

      <section aria-label="Processos do cliente">
        <h2 className="mb-4 font-heading text-sm font-bold tracking-wider uppercase">
          Histórico de viagens · {processos.length}
        </h2>
        {processos.length === 0 ? (
          <div className="grid place-items-center rounded-2xl border border-dashed bg-card px-6 py-12 text-center">
            <Plane className="size-8 text-marca" />
            <p className="mt-3 font-heading font-bold">Nenhuma viagem ainda</p>
            <p className="mt-1 text-sm text-muted-foreground">Abra o primeiro processo deste cliente.</p>
          </div>
        ) : (
          <ol className="space-y-3">
            {processos.map((p) => (
              <li key={p.processo_id}>
                <Link
                  href={`/processos/${p.processo_id}`}
                  className="group flex overflow-hidden rounded-2xl border bg-card transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  {/* canhoto do cartão de embarque */}
                  <div className="flex w-28 shrink-0 flex-col justify-between bg-tinta p-4 text-papel">
                    <span className="font-heading text-lg font-extrabold tracking-widest">{p.tipo}</span>
                    <span className="font-heading text-xs font-bold tracking-wider text-marca">
                      #{p.processo_id}
                    </span>
                  </div>
                  <div className="flex flex-1 flex-wrap items-center gap-x-6 gap-y-2 border-l-2 border-dashed px-5 py-4">
                    <div className="min-w-40">
                      <p className="text-xs text-muted-foreground">{TIPOS[p.tipo].nome}</p>
                      <div className="mt-1 flex flex-wrap gap-2">
                        <SeloSituacao situacao={p.situacao} />
                        <SeloResultado resultado={p.resultado_geral} />
                      </div>
                    </div>
                    {datasPrincipais(p).map((d) => (
                      <div key={d.rotulo}>
                        <p className="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase">
                          {d.rotulo}
                        </p>
                        <p className="font-medium tabular-nums">{formatarData(d.valor)}</p>
                      </div>
                    ))}
                    <p className="ml-auto flex items-center gap-1 text-sm text-muted-foreground">
                      <Users className="size-4" /> {p.n_solicitantes}
                    </p>
                  </div>
                </Link>
              </li>
            ))}
          </ol>
        )}
      </section>

      {pode(usuario.perfil, "administrar") && (
        <Suspense fallback={<EsqueletoHistorico />}>
          <HistoricoAlteracoes filtro={{ cliente_id: cliente.id }} />
        </Suspense>
      )}
    </>
  );
}

function Esqueleto() {
  return (
    <div aria-hidden>
      <Skeleton className="h-4 w-24" />
      <Skeleton className="mt-4 h-9 w-72" />
      <Skeleton className="mt-3 mb-8 h-5 w-96" />
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-24 rounded-2xl" />
        ))}
      </div>
    </div>
  );
}
