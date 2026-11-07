"use client";

import { Check, Copy, Eye, EyeOff, Wand2 } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { gerarSenha, SENHA_MINIMA } from "@/lib/usuarios";
import { cn } from "@/lib/utils";

/**
 * Campo de senha com "mostrar", e (opcional) "gerar" e "copiar": o admin gera uma senha forte e copia para
 * mandar à pessoa. A senha só existe aqui na tela: a API guarda só o hash.
 */
export function CampoSenha({
  rotulo,
  valor,
  aoMudar,
  erro,
  comGerador = false,
  autoComplete = "new-password",
  dica,
}: {
  rotulo: string;
  valor: string;
  aoMudar: (v: string) => void;
  erro?: string;
  comGerador?: boolean;
  autoComplete?: "new-password" | "current-password";
  dica?: string;
}) {
  const id = useId();
  const [visivel, setVisivel] = useState(false);
  const [copiada, setCopiada] = useState(false);

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(valor);
      setCopiada(true);
      setTimeout(() => setCopiada(false), 1800);
    } catch {
      setVisivel(true); // sem acesso à área de transferência: ao menos mostra para copiar à mão
    }
  };

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{rotulo}</Label>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Input
            id={id}
            type={visivel ? "text" : "password"}
            value={valor}
            onChange={(e) => aoMudar(e.target.value)}
            autoComplete={autoComplete}
            aria-invalid={Boolean(erro)}
            aria-describedby={erro ? `${id}-erro` : undefined}
            className={cn("h-10 pr-10", visivel && "font-mono tracking-wide")}
          />
          <button
            type="button"
            onClick={() => setVisivel((v) => !v)}
            aria-label={visivel ? "Esconder a senha" : "Mostrar a senha"}
            className="absolute top-1/2 right-2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            {visivel ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </div>
        {comGerador && (
          <>
            <Button
              type="button"
              variant="outline"
              className="h-10"
              onClick={() => {
                aoMudar(gerarSenha());
                setVisivel(true);
              }}
            >
              <Wand2 className="size-4" /> Gerar
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon-lg"
              className="size-10"
              disabled={!valor}
              onClick={copiar}
              aria-label={copiada ? "Senha copiada" : "Copiar a senha"}
            >
              {copiada ? <Check className="size-4 text-sucesso" /> : <Copy className="size-4" />}
            </Button>
          </>
        )}
      </div>
      {erro ? (
        <p id={`${id}-erro`} className="text-xs font-medium text-perigo">
          {erro}
        </p>
      ) : (
        dica !== "" && (
          <p className="text-xs text-muted-foreground">{dica ?? `Pelo menos ${SENHA_MINIMA} caracteres.`}</p>
        )
      )}
    </div>
  );
}
