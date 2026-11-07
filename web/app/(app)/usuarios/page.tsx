import { ShieldX } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { Tripulacao } from "@/components/usuarios/tripulacao";
import { apiGet } from "@/lib/api";
import { pode } from "@/lib/permissoes";
import { usuarioAtual } from "@/lib/sessao";
import type { Usuario } from "@/lib/tipos";

export const metadata: Metadata = { title: "Usuários" };

/** Quem entra no sistema e com qual perfil. Só admin (a API recusa os demais com 403). */
export default function PaginaUsuarios() {
  return (
    <div className="mx-auto max-w-6xl">
      <header className="mb-6">
        <h1 className="text-3xl font-extrabold">Usuários</h1>
        <p className="mt-1 text-muted-foreground">
          A tripulação da Concept Vistos: quem entra e o que pode fazer.
        </p>
      </header>
      <Suspense fallback={<Esqueleto />}>
        <Conteudo />
      </Suspense>
    </div>
  );
}

async function Conteudo() {
  const eu = await usuarioAtual();
  if (!pode(eu.perfil, "administrar"))
    return (
      <div className="grid place-items-center gap-3 rounded-2xl border border-dashed p-12 text-center">
        <ShieldX className="size-10 text-muted-foreground" aria-hidden />
        <p className="font-semibold">Área só para administradores.</p>
        <p className="text-sm text-muted-foreground">
          Fale com um administrador se precisar de outro acesso.
        </p>
      </div>
    );
  const usuarios = await apiGet<Usuario[]>("/usuarios");
  return <Tripulacao usuarios={usuarios} euId={eu.id} />;
}

function Esqueleto() {
  return (
    <div aria-hidden>
      <div className="mb-6 flex justify-between">
        <Skeleton className="h-11 w-80 rounded-xl" />
        <Skeleton className="h-11 w-72 rounded-xl" />
      </div>
      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-40 rounded-2xl" />
        ))}
      </div>
    </div>
  );
}
