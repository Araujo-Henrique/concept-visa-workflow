import type { Metadata } from "next";
import { Suspense } from "react";

import { CenaVoo } from "@/components/login/cena-voo";
import { FormLogin } from "@/components/login/form-login";
import { Simbolo } from "@/components/marca/simbolo";
import { destinoSeguro } from "@/lib/erros";
import { mensagemDoErroGoogle } from "@/lib/google-oauth";

export const metadata: Metadata = { title: "Entrar" };

/** Lê a URL (para onde voltar, sessão expirada): dado da requisição, por isso fica num <Suspense>. */
async function Formulario({ searchParams }: { searchParams: PageProps<"/login">["searchParams"] }) {
  const { de, expirou, erro } = await searchParams;
  return (
    <FormLogin
      destino={destinoSeguro(typeof de === "string" ? de : null)}
      expirou={expirou === "1"}
      erroGoogle={mensagemDoErroGoogle(typeof erro === "string" ? erro : null)}
    />
  );
}

export default function PaginaLogin({ searchParams }: PageProps<"/login">) {
  return (
    <main className="grid min-h-dvh lg:grid-cols-[1.15fr_1fr]">
      <section>
        <CenaVoo />
      </section>

      <section className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <Simbolo className="mb-6 h-12" />
          <h1 className="text-3xl font-extrabold">Boas-vindas de volta</h1>
          <p className="mt-2 mb-8 text-muted-foreground">
            Entre para acompanhar os processos de visto e passaporte.
          </p>
          <Suspense fallback={<div className="h-64" />}>
            <Formulario searchParams={searchParams} />
          </Suspense>
          <p className="mt-10 text-xs text-muted-foreground">
            Problemas para entrar? Fale com um administrador da Concept Vistos.
          </p>
        </div>
      </section>
    </main>
  );
}
