import Link from "next/link";

import { Simbolo } from "@/components/marca/simbolo";

export default function ProcessoNaoEncontrado() {
  return (
    <div className="mx-auto grid max-w-md place-items-center py-24 text-center">
      <Simbolo className="h-16 opacity-60" />
      <h1 className="mt-6 text-2xl font-extrabold">Processo não encontrado</h1>
      <p className="mt-2 text-muted-foreground">Esse número não existe ou o processo foi removido.</p>
      <Link href="/processos" className="mt-6 font-medium text-marca-forte hover:underline">
        Voltar aos processos
      </Link>
    </div>
  );
}
