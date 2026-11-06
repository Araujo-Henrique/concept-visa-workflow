"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { rotuloSituacao } from "@/lib/formatos";

/** Reabrir um processo concluído exige um motivo curto (regra da API: vira o evento "reaberto"). */
export function DialogoMotivo({
  aberto,
  destino,
  aoConfirmar,
  aoCancelar,
}: {
  aberto: boolean;
  destino: string | null;
  aoConfirmar: (motivo: string) => void;
  aoCancelar: () => void;
}) {
  const [motivo, setMotivo] = useState("");
  const valido = motivo.trim().length > 0;

  return (
    <Dialog
      open={aberto}
      onOpenChange={(abrir) => {
        if (!abrir) {
          setMotivo("");
          aoCancelar();
        }
      }}
    >
      <DialogContent>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!valido) return;
            aoConfirmar(motivo.trim());
            setMotivo("");
          }}
        >
          <DialogHeader>
            <DialogTitle>Reabrir processo concluído</DialogTitle>
            <DialogDescription>
              Ele volta para <strong>{destino ? rotuloSituacao(destino) : ""}</strong>. Conte em poucas
              palavras o motivo: fica registrado no histórico.
            </DialogDescription>
          </DialogHeader>
          <div className="my-5 space-y-2">
            <Label htmlFor="motivo">Motivo</Label>
            <Textarea
              id="motivo"
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              placeholder="Ex.: visto negado, nova tentativa"
              autoFocus
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={aoCancelar}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!valido}>
              Reabrir
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
