import { Check, TriangleAlert } from "lucide-react";

import { ESTADOS_DO_DESPACHO, type EstadoDespacho } from "@/lib/agenda";
import { rotuloSituacao } from "@/lib/formatos";
import {
  CLASSES_DO_TOM,
  formatarData,
  rotuloResultado,
  tomDaSituacao,
  tomDoResultado,
} from "@/lib/processos";
import { cn } from "@/lib/utils";

const BASE =
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap";

export function SeloSituacao({ situacao, className }: { situacao: string; className?: string }) {
  const tom = tomDaSituacao(situacao);
  return (
    <span className={cn(BASE, CLASSES_DO_TOM[tom], className)}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {rotuloSituacao(situacao)}
    </span>
  );
}

export function SeloResultado({ resultado, className }: { resultado: string; className?: string }) {
  return (
    <span className={cn(BASE, CLASSES_DO_TOM[tomDoResultado(resultado)], className)}>
      {rotuloResultado(resultado)}
    </span>
  );
}

/** Código de consulado como código de aeroporto (POA, SP, RIO...), no estilo do cartão de embarque. */
export function SeloConsulado({ consulado }: { consulado: string | null | undefined }) {
  if (!consulado) return <span className="text-muted-foreground">—</span>;
  return (
    <span className="rounded-md border px-1.5 py-0.5 font-heading text-[11px] font-bold tracking-widest">
      {consulado}
    </span>
  );
}

/** Estado do despacho de um REN: feito (com a data), atrasado ou a despachar. */
export function SeloDespacho({
  estado,
  despachadoEm,
  className,
}: {
  estado: EstadoDespacho | null;
  despachadoEm?: string | null;
  className?: string;
}) {
  if (!estado) return null;
  const { rotulo, classes } = ESTADOS_DO_DESPACHO[estado];
  return (
    <span className={cn(BASE, classes, className)}>
      {estado === "feito" ? <Check className="size-3" aria-hidden /> : null}
      {estado === "atrasado" ? <TriangleAlert className="size-3" aria-hidden /> : null}
      {rotulo}
      {estado === "feito" && despachadoEm ? ` em ${formatarData(despachadoEm)}` : null}
    </span>
  );
}
