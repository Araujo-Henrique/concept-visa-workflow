"use client";

import { PackageCheck, Truck } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { editarProcesso } from "@/app/acoes/processos";
import { CampoTexto } from "@/components/formularios/campos";
import { SeloDespacho } from "@/components/processos/selos";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { estadoDoDespacho } from "@/lib/agenda";
import { formatarData } from "@/lib/processos";
import { cn } from "@/lib/utils";

type Props = {
  processoId: number;
  /** prazo calculado pelo banco (CASV - 7) */
  prazo: string | null;
  despachadoEm: string | null;
  rastreio: string | null;
  /** "AAAA-MM-DD" de Brasília, vindo do servidor */
  hoje: string;
  podeMarcar: boolean;
};

/**
 * Faixa do despacho na página de dados do REN: o estado (feito, atrasado, a despachar) e, para quem pode
 * escrever, o botão que grava a data do despacho e o código de rastreio de uma vez.
 */
export function FaixaDespacho({ processoId, prazo, despachadoEm, rastreio, hoje, podeMarcar }: Props) {
  const estado = estadoDoDespacho(prazo, despachadoEm, hoje);
  const [aberto, setAberto] = useState(false);
  const [data, setData] = useState(hoje);
  const [codigo, setCodigo] = useState(rastreio ?? "");
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, iniciar] = useTransition();

  if (!estado && !podeMarcar) return null;

  const abrir = () => {
    setData(hoje);
    setCodigo(rastreio ?? "");
    setErro(null);
    setAberto(true);
  };

  const salvar = () => {
    if (!data) return setErro("Informe a data do despacho.");
    if (data > hoje) return setErro("A data do despacho não pode ser no futuro.");
    iniciar(async () => {
      const mudancas: Record<string, unknown> = { despachado_em: data };
      if (codigo.trim() !== (rastreio ?? "")) mudancas.codigo_rastreio = codigo.trim() || null;
      const r = await editarProcesso("REN", processoId, mudancas);
      if (r.ok) {
        toast.success("Despacho registrado", { description: `Em ${formatarData(data)}` });
        setAberto(false);
      } else setErro(r.erro);
    });
  };

  return (
    <div
      className={cn(
        "mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-dashed p-3",
        estado === "atrasado" && "border-perigo/40 bg-perigo-suave/40",
      )}
    >
      <div className="flex items-center gap-3">
        {estado === "feito" ? (
          <PackageCheck className="size-5 text-sucesso" aria-hidden />
        ) : (
          <Truck className="size-5 text-muted-foreground" aria-hidden />
        )}
        <div>
          <p className="text-[10px] font-semibold tracking-[0.15em] text-muted-foreground uppercase">
            Despacho
          </p>
          <p className="mt-0.5 flex flex-wrap items-center gap-2 text-sm">
            <SeloDespacho estado={estado} despachadoEm={despachadoEm} />
            {estado !== "feito" &&
              (prazo ? (
                <span className="text-muted-foreground">prazo {formatarData(prazo)}</span>
              ) : (
                <span className="text-muted-foreground">sem CASV marcado, ainda sem prazo</span>
              ))}
          </p>
        </div>
      </div>
      {podeMarcar && estado !== "feito" && (
        <Button size="sm" onClick={abrir}>
          <PackageCheck className="size-3.5" /> Marcar como despachado
        </Button>
      )}

      <Dialog open={aberto} onOpenChange={setAberto}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Registrar o despacho</DialogTitle>
            <DialogDescription>
              Para corrigir ou desfazer depois, use &quot;Editar dados&quot; (campo &quot;Despachado
              em&quot;).
            </DialogDescription>
          </DialogHeader>
          <form
            className="space-y-4"
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              salvar();
            }}
          >
            <CampoTexto rotulo="Despachado em" tipo="date" valor={data} aoMudar={setData} />
            <CampoTexto
              rotulo="Código de rastreio"
              valor={codigo}
              aoMudar={setCodigo}
              placeholder="Opcional"
            />
            {erro && (
              <p role="alert" className="rounded-lg bg-perigo-suave px-3 py-2 text-sm text-perigo">
                {erro}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setAberto(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={salvando}>
                {salvando ? "Salvando…" : "Registrar despacho"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
