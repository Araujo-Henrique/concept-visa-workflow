"use client";

import { Eye, EyeOff, Plane } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useActionState, useEffect, useState } from "react";

import { entrar, type EstadoLogin } from "@/app/acoes/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** O "G" oficial de quatro cores (o Google exige as cores originais no botão de login). */
function IconeGoogle() {
  return (
    <svg viewBox="0 0 48 48" className="size-5" aria-hidden>
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}

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

export function FormLogin({
  destino,
  expirou,
  erroGoogle,
}: {
  destino: string;
  expirou: boolean;
  /** por que o login com o Google voltou sem entrar (já em português), se voltou */
  erroGoogle?: string;
}) {
  const [estado, acao, pendente] = useActionState<EstadoLogin, FormData>(entrar, undefined);
  const [verSenha, setVerSenha] = useState(false);
  // o acesso por senha é o reserva do administrador: fica recolhido, a não ser que a pessoa o abra
  const [abrirSenha, setAbrirSenha] = useState(false);
  const mostrarSenha = abrirSenha || Boolean(estado);
  const irParaOGoogle = `/api/auth/google${destino !== "/" ? `?de=${encodeURIComponent(destino)}` : ""}`;
  const router = useRouter();

  useEffect(() => {
    if (!estado?.ok) return;
    const t = setTimeout(() => router.replace(destino), 1100); // tempo do carimbo
    return () => clearTimeout(t);
  }, [estado, destino, router]);

  return (
    <div className="relative">
      <AnimatePresence>{estado?.ok && <Carimbo nome={estado.primeiroNome} />}</AnimatePresence>

      <div className="space-y-4">
        {expirou && !estado && (
          <p className="rounded-lg bg-alerta-suave px-3 py-2 text-sm text-alerta">
            Sua sessão expirou. Entre novamente para continuar de onde parou.
          </p>
        )}
        {erroGoogle && !estado && (
          <p role="alert" className="rounded-lg bg-perigo-suave px-3 py-2 text-sm text-perigo">
            {erroGoogle}
          </p>
        )}

        <Button asChild variant="outline" className="h-11 w-full gap-3 text-base">
          {/* link comum (não <Link>): é uma navegação para fora do app, sem pré-carregar */}
          <a href={irParaOGoogle}>
            <IconeGoogle /> Entrar com o Google
          </a>
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          Use o e-mail cadastrado pela Concept Vistos. Quem não estiver cadastrado não entra.
        </p>

        {!mostrarSenha && (
          <button
            type="button"
            onClick={() => setAbrirSenha(true)}
            aria-expanded={false}
            aria-controls="form-senha"
            className="mx-auto block text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Sou administrador e entro com senha
          </button>
        )}
      </div>

      {mostrarSenha && (
        <form id="form-senha" action={acao} className="mt-6 space-y-5 border-t border-dashed pt-6" noValidate>
          <p className="text-sm font-medium">Acesso do administrador</p>
          <div className="space-y-2">
            <Label htmlFor="email">E-mail</Label>
            <Input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              autoFocus={abrirSenha}
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
      )}
    </div>
  );
}
