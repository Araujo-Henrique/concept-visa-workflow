"use client";

import { Check, Plane, Stamp } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { mudarSituacao } from "@/app/acoes/processos";
import { DialogoMotivo } from "@/components/processos/dialogo-motivo";
import { Button } from "@/components/ui/button";
import { rotuloSituacao } from "@/lib/formatos";
import { tomDaSituacao } from "@/lib/processos";
import { cn } from "@/lib/utils";

/**
 * A rota do processo: cada situação é uma parada. A atual tem o avião; as já visitadas, um check.
 * Clicar numa parada pede confirmação e "carimba" a mudança (sair de Concluído pede o motivo).
 */
export function RotaSituacao({
  processoId,
  atual,
  situacoes,
  visitadas,
  podeMudar,
  aoCarimbar,
}: {
  processoId: number;
  atual: string;
  situacoes: string[];
  visitadas: Set<string>;
  podeMudar: boolean;
  aoCarimbar: (eventoId: number) => void;
}) {
  const [escolhida, setEscolhida] = useState<string | null>(null);
  const [pedirMotivo, setPedirMotivo] = useState(false);
  const [salvando, iniciar] = useTransition();

  function carimbar(para: string, motivo?: string) {
    iniciar(async () => {
      const r = await mudarSituacao(processoId, para, motivo);
      if (r.ok && r.dados) {
        toast.success("Carimbado!", { description: `${rotuloSituacao(atual)} → ${rotuloSituacao(para)}` });
        setEscolhida(null);
        aoCarimbar(r.dados.id);
      } else if (!r.ok) {
        toast.error("Não deu para mudar a situação", { description: r.erro });
      }
    });
  }

  function confirmar() {
    if (!escolhida) return;
    if (atual === "Concluido") setPedirMotivo(true);
    else carimbar(escolhida);
  }

  return (
    <aside className="rounded-2xl border bg-card p-5" aria-label="Rota do processo">
      <h2 className="font-heading text-sm font-bold tracking-wider uppercase">Rota do processo</h2>
      <p className="mt-1 mb-5 text-xs text-muted-foreground">
        {podeMudar ? "Escolha a próxima parada para carimbar." : "Seu perfil só consulta a rota."}
      </p>

      <ol className="relative space-y-1 before:absolute before:top-3 before:bottom-3 before:left-[15px] before:w-0.5 before:bg-[repeating-linear-gradient(to_bottom,var(--border)_0_6px,transparent_6px_10px)]">
        {situacoes.map((s) => {
          const eAtual = s === atual;
          const visitada = !eAtual && visitadas.has(s);
          const selecionada = s === escolhida;
          const concluido = tomDaSituacao(s) === "concluido";
          return (
            <li key={s} className="relative">
              <button
                type="button"
                disabled={!podeMudar || eAtual || salvando}
                onClick={() => setEscolhida(selecionada ? null : s)}
                aria-current={eAtual ? "step" : undefined}
                aria-pressed={selecionada}
                className={cn(
                  "flex w-full items-center gap-3 rounded-xl py-1.5 pr-2 text-left text-sm transition-colors",
                  !eAtual && podeMudar && "hover:bg-muted",
                  selecionada && "bg-marca-suave",
                )}
              >
                <span
                  className={cn(
                    "relative z-10 grid size-8 shrink-0 place-items-center rounded-full border-2 bg-card transition-colors",
                    eAtual && "border-marca bg-marca text-tinta",
                    visitada && "border-marca-forte/50 text-marca-forte",
                    selecionada && "border-marca",
                    concluido && !eAtual && "border-dashed",
                  )}
                >
                  {eAtual ? (
                    <Plane className="size-4" />
                  ) : visitada ? (
                    <Check className="size-3.5" />
                  ) : (
                    <span className="size-1.5 rounded-full bg-muted-foreground/40" />
                  )}
                  {eAtual && <span className="absolute inset-0 animate-ping rounded-full bg-marca/30" />}
                </span>
                <span
                  className={cn(
                    eAtual ? "font-bold" : visitada ? "text-foreground" : "text-muted-foreground",
                  )}
                >
                  {rotuloSituacao(s)}
                </span>
                {eAtual && (
                  <span className="ml-auto text-[10px] font-semibold tracking-wider text-marca-forte uppercase">
                    agora
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ol>

      {escolhida && (
        <div className="mt-5 rounded-xl border border-dashed border-marca p-3">
          <p className="text-sm">
            Mover de <strong>{rotuloSituacao(atual)}</strong> para{" "}
            <strong>{rotuloSituacao(escolhida)}</strong>?
          </p>
          <div className="mt-3 flex gap-2">
            <Button size="sm" onClick={confirmar} disabled={salvando} className="flex-1">
              <Stamp className="size-4" /> {salvando ? "Carimbando…" : "Carimbar"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEscolhida(null)} disabled={salvando}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

      <DialogoMotivo
        aberto={pedirMotivo}
        destino={escolhida}
        aoCancelar={() => setPedirMotivo(false)}
        aoConfirmar={(motivo) => {
          setPedirMotivo(false);
          if (escolhida) carimbar(escolhida, motivo);
        }}
      />
    </aside>
  );
}
