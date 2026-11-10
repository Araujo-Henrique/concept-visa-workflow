import { LogIn, Mail, ShieldCheck } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { TrocarSenha } from "@/components/usuarios/trocar-senha";
import { NOME_DO_PERFIL } from "@/lib/permissoes";
import { usuarioAtual } from "@/lib/sessao";
import { DESCRICAO_DO_PERFIL, iniciais, temSenha } from "@/lib/usuarios";

export const metadata: Metadata = { title: "Minha conta" };

/** Minha conta: o próprio crachá (nome, e-mail, perfil) e, para o administrador, a troca de senha. */
export default function PaginaConta() {
  return (
    <div className="mx-auto max-w-4xl">
      <header className="mb-8">
        <h1 className="text-3xl font-extrabold">Minha conta</h1>
        <p className="mt-1 text-muted-foreground">Seus dados de acesso.</p>
      </header>
      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <Suspense fallback={<Skeleton className="h-64 rounded-2xl" />}>
          <MeuCracha />
        </Suspense>
        <Suspense fallback={<Skeleton className="h-64 rounded-2xl" />}>
          <CartaoDeAcesso />
        </Suspense>
      </div>
    </div>
  );
}

/** Administrador troca a senha; os demais entram com o Google e não têm senha para trocar. */
async function CartaoDeAcesso() {
  const eu = await usuarioAtual();
  if (!temSenha(eu.perfil)) {
    return (
      <section
        className="self-start rounded-2xl border bg-card p-6 shadow-sm"
        aria-labelledby="titulo-acesso"
      >
        <h2 id="titulo-acesso" className="flex items-center gap-2 text-lg font-bold">
          <LogIn className="size-5 text-marca" aria-hidden /> Como você entra
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Você entra com a sua conta do Google, usando o e-mail {eu.email}. Não existe senha deste sistema
          para trocar: a segurança da sua conta é a do Google (senha e verificação em duas etapas).
        </p>
      </section>
    );
  }
  return (
    <section className="rounded-2xl border bg-card p-6 shadow-sm" aria-labelledby="titulo-senha">
      <h2 id="titulo-senha" className="text-lg font-bold">
        Trocar senha
      </h2>
      <p className="mb-5 text-sm text-muted-foreground">
        A senha é o seu acesso reserva de administrador (o normal é entrar com o Google). Depois de trocar, a
        sessão atual continua aberta; a senha nova vale no próximo login.
      </p>
      <TrocarSenha />
    </section>
  );
}

async function MeuCracha() {
  const eu = await usuarioAtual();
  return (
    <section
      className="self-start overflow-hidden rounded-2xl border bg-card shadow-sm"
      aria-label="Seu crachá"
    >
      <div className="relative h-14 bg-tinta dark:bg-muted">
        <span
          className="absolute top-4 left-1/2 h-2 w-12 -translate-x-1/2 rounded-full bg-background"
          aria-hidden
        />
      </div>
      <div className="flex flex-col items-center px-6 pt-0 pb-6 text-center">
        <span
          className="relative z-10 -mt-8 grid size-16 place-items-center rounded-full bg-marca font-heading text-xl font-extrabold text-tinta ring-4 ring-card"
          aria-hidden
        >
          {iniciais(eu.nome)}
        </span>
        <p className="mt-3 text-xl font-bold">{eu.nome}</p>
        <p className="mt-1 inline-flex items-center gap-1.5 text-sm text-muted-foreground">
          <Mail className="size-4" aria-hidden /> {eu.email}
        </p>
        <div className="mt-5 w-full rounded-xl bg-marca-suave p-3 text-left">
          <p className="flex items-center gap-2 font-heading text-xs font-bold tracking-[0.2em] text-accent-foreground uppercase">
            <ShieldCheck className="size-4" aria-hidden /> {NOME_DO_PERFIL[eu.perfil]}
          </p>
          <p className="mt-1 text-sm text-accent-foreground">{DESCRICAO_DO_PERFIL[eu.perfil]}</p>
        </div>
        <p className="mt-4 text-xs text-muted-foreground">
          Nome, e-mail e perfil quem muda é um administrador.
        </p>
      </div>
    </section>
  );
}
