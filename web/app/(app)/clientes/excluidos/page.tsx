import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ListaExcluidos, Lapides, VoltarAosClientes } from "@/components/clientes/excluidos";
import { Skeleton } from "@/components/ui/skeleton";
import { apiLista } from "@/lib/api";
import type { Alteracao, ClienteExcluido } from "@/lib/auditoria";
import { pode } from "@/lib/permissoes";
import { usuarioAtual } from "@/lib/sessao";

export const metadata: Metadata = { title: "Clientes excluídos" };

export default function PaginaExcluidos() {
  return (
    <div className="mx-auto max-w-4xl">
      <VoltarAosClientes />
      <header className="mt-3 mb-6">
        <h1 className="text-3xl font-extrabold">Clientes excluídos</h1>
        <p className="mt-1 text-muted-foreground">
          Quem foi excluído por engano volta daqui, com processos, pessoas, DS-160 e histórico. Só
          administradores veem esta tela.
        </p>
      </header>
      <Suspense fallback={<Esqueleto />}>
        <Conteudo />
      </Suspense>
    </div>
  );
}

async function Conteudo() {
  const usuario = await usuarioAtual();
  if (!pode(usuario.perfil, "administrar")) notFound(); // a API também recusa (403)

  const [{ itens: excluidos }, { itens: eliminacoes }] = await Promise.all([
    apiLista<ClienteExcluido>("/auditoria/apagados", { limit: 200 }),
    apiLista<Alteracao>("/auditoria", { tabela: "clientes", acao: "eliminou", limit: 50 }),
  ]);

  return (
    <>
      <ListaExcluidos clientes={excluidos} />
      <Lapides
        itens={eliminacoes.map((e) => ({
          id: e.id,
          registro_id: e.registro_id,
          usuario_nome: e.usuario_nome,
          criado_em: e.criado_em,
          motivo: String(e.depois?.motivo ?? "—"),
        }))}
      />
    </>
  );
}

function Esqueleto() {
  return (
    <div className="space-y-3" aria-hidden>
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-28 rounded-2xl" />
      ))}
    </div>
  );
}
