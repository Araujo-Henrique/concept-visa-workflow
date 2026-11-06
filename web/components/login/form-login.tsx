"use client";

import { Eye, EyeOff, Plane } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useActionState, useEffect, useState } from "react";

import { entrar, type EstadoLogin } from "@/app/acoes/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** Carimbo de passaporte que "bate" na tela ao entrar. */
function Carimbo({ nome }: { nome?: string }) {
  return (
    <motion.div
      role="status"
      className="pointer-events-none absolute inset-0 z-20 grid place-items-center bg-card/80 backdrop-blur-[2px]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <motion.div
        initial={{ scale: 2.4, rotate: -24, opacity: 0 }}
        animate={{ scale: 1, rotate: -12, opacity: 1 }}
        transition={{ type: "spring", stiffness: 520, damping: 22 }}
        className="grid size-44 place-items-center rounded-full border-[5px] border-double border-marca-forte text-center text-marca-forte"
      >
        <div className="font-heading uppercase">
          <p className="text-[10px] font-bold tracking-[0.3em]">Concept Vistos</p>
          <p className="my-1 text-xl font-extrabold leading-none">Bem-vindo{nome ? "," : ""}</p>
          {nome && <p className="text-lg font-extrabold leading-none">{nome}</p>}
          <p className="mt-1 text-[10px] font-bold tracking-[0.3em]">Embarque liberado</p>
        </div>
      </motion.div>
    </motion.div>
  );
}

export function FormLogin({ destino, expirou }: { destino: string; expirou: boolean }) {
  const [estado, acao, pendente] = useActionState<EstadoLogin, FormData>(entrar, undefined);
  const [verSenha, setVerSenha] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (!estado?.ok) return;
    const t = setTimeout(() => router.replace(destino), 1100); // tempo do carimbo
    return () => clearTimeout(t);
  }, [estado, destino, router]);

  return (
    <div className="relative">
      <AnimatePresence>{estado?.ok && <Carimbo nome={estado.primeiroNome} />}</AnimatePresence>

      <form action={acao} className="space-y-5" noValidate>
        {expirou && !estado && (
          <p className="rounded-lg bg-alerta-suave px-3 py-2 text-sm text-alerta">
            Sua sessão expirou. Entre novamente para continuar de onde parou.
          </p>
        )}

        <div className="space-y-2">
          <Label htmlFor="email">E-mail</Label>
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            autoFocus
            className="h-11"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="senha">Senha</Label>
          <div className="relative">
            <Input
              id="senha"
              name="senha"
              type={verSenha ? "text" : "password"}
              autoComplete="current-password"
              required
              className="h-11 pr-11"
            />
            <button
              type="button"
              onClick={() => setVerSenha((v) => !v)}
              className="absolute inset-y-0 right-0 grid w-11 place-items-center text-muted-foreground hover:text-foreground"
              aria-label={verSenha ? "Esconder senha" : "Mostrar senha"}
            >
              {verSenha ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </div>

        <p aria-live="polite" className="min-h-5 text-sm font-medium text-perigo">
          {estado?.erro}
        </p>

        <Button type="submit" disabled={pendente || estado?.ok} className="group h-11 w-full text-base">
          {pendente ? "Embarcando…" : "Entrar"}
          <Plane
            className={`size-4 transition-transform ${pendente ? "translate-x-1 -translate-y-0.5" : "group-hover:translate-x-1"}`}
          />
        </Button>
      </form>
    </div>
  );
}
