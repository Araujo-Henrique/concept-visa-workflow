"use client";

import { useId, type ReactNode } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

/** O Select do Radix não aceita valor "": este valor interno representa "nenhum". */
const VAZIO = "__vazio";

type Base = { rotulo: string; erro?: string; dica?: string; className?: string; obrigatorio?: boolean };

function Moldura({
  id,
  rotulo,
  erro,
  dica,
  className,
  obrigatorio,
  children,
}: Base & { id: string; children: ReactNode }) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={id}>
        {rotulo}
        {obrigatorio && <span className="text-perigo"> *</span>}
      </Label>
      {children}
      {erro ? (
        <p id={`${id}-erro`} className="text-xs font-medium text-perigo">
          {erro}
        </p>
      ) : (
        dica && <p className="text-xs text-muted-foreground">{dica}</p>
      )}
    </div>
  );
}

export function CampoTexto({
  valor,
  aoMudar,
  tipo = "text",
  placeholder,
  multilinha = false,
  autoFocus,
  ...base
}: Base & {
  valor: string;
  aoMudar: (v: string) => void;
  tipo?: "text" | "email" | "tel" | "date";
  placeholder?: string;
  multilinha?: boolean;
  autoFocus?: boolean;
}) {
  const id = useId();
  const comum = {
    id,
    value: valor,
    placeholder,
    autoFocus,
    "aria-invalid": Boolean(base.erro),
    "aria-describedby": base.erro ? `${id}-erro` : undefined,
  };
  return (
    <Moldura id={id} {...base}>
      {multilinha ? (
        <Textarea {...comum} rows={3} onChange={(e) => aoMudar(e.target.value)} />
      ) : (
        <Input {...comum} type={tipo} className="h-10" onChange={(e) => aoMudar(e.target.value)} />
      )}
    </Moldura>
  );
}

export function CampoSelecao({
  valor,
  aoMudar,
  opcoes,
  permiteVazio = false,
  rotuloVazio = "—",
  ...base
}: Base & {
  valor: string;
  aoMudar: (v: string) => void;
  opcoes: [valor: string, rotulo: string][];
  permiteVazio?: boolean;
  rotuloVazio?: string;
}) {
  const id = useId();
  return (
    <Moldura id={id} {...base}>
      <Select value={valor || VAZIO} onValueChange={(v) => aoMudar(v === VAZIO ? "" : v)}>
        <SelectTrigger id={id} className="h-10 w-full" aria-invalid={Boolean(base.erro)}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {(permiteVazio || !valor) && <SelectItem value={VAZIO}>{rotuloVazio}</SelectItem>}
          {opcoes.map(([v, r]) => (
            <SelectItem key={v} value={v}>
              {r}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Moldura>
  );
}
