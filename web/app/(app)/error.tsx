"use client";

import { RotateCcw } from "lucide-react";
import Link from "next/link";

import { Simbolo } from "@/components/marca/simbolo";
import { Button } from "@/components/ui/button";

/**
 * Erro inesperado numa tela da área logada: o menu continua no lugar e a pessoa pode tentar de novo
 * (busca os dados outra vez). Em produção o Next não repassa a mensagem do servidor; o código (digest)
 * ajuda a achar o erro no log da API/Next.
 */
export default function ErroDaTela({ error, retry }: { error: unknown; retry: () => void }) {
  const digest = (error as { digest?: string } | null)?.digest;
  const mensagem = process.env.NODE_ENV === "development" && error instanceof Error ? error.message : null;

  return (
    <div className="mx-auto grid max-w-md place-items-center py-24 text-center">
      <Simbolo className="h-16 -rotate-12 opacity-70" />
      <h1 className="mt-6 text-2xl font-extrabold">Turbulência no caminho</h1>
      <p className="mt-2 text-muted-foreground">
        Não consegui carregar esta tela agora. Tente de novo; se continuar, avise quem cuida do sistema.
      </p>
      {mensagem && <p className="mt-3 rounded-lg bg-muted px-3 py-2 text-sm">{mensagem}</p>}
      <div className="mt-6 flex gap-3">
        <Button onClick={() => retry()}>
          <RotateCcw className="size-4" /> Tentar de novo
        </Button>
        <Button variant="ghost" asChild>
          <Link href="/processos">Ir para processos</Link>
        </Button>
      </div>
      {digest && <p className="mt-6 font-mono text-xs text-muted-foreground">código: {digest}</p>}
    </div>
  );
}
