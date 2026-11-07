"use client";

import { Clock } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { renovarSessao, sair } from "@/app/acoes/auth";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { COOKIE_EXPIRA } from "@/lib/constantes";
import { contagem, decidir, INTERVALO_DE_CHECAGEM, lerExpiracao, urlDoLogin } from "@/lib/sessao-viva";

const SINAIS_DE_USO = ["pointerdown", "keydown", "wheel", "touchstart"] as const;

/**
 * Mantém a sessão viva enquanto a pessoa usa o sistema (sessão deslizante) e avisa antes de vencer quando
 * ela está parada. Vencida, leva ao login guardando a tela atual. A regra fica em lib/sessao-viva.ts.
 */
export function GuardaSessao() {
  const ultimaAtividade = useRef(0);
  const ultimaRenovacao = useRef(0);
  const renovando = useRef(false);
  const [noLimite, setNoLimite] = useState(false);
  const [aviso, setAviso] = useState<number | null>(null); // ms que faltam, quando o aviso está aberto
  const limiteRef = useRef(false);

  const irParaLogin = useCallback(() => {
    window.location.assign(urlDoLogin(window.location.pathname + window.location.search));
  }, []);

  const renovar = useCallback(async () => {
    if (renovando.current) return;
    renovando.current = true;
    try {
      const r = await renovarSessao();
      ultimaRenovacao.current = Date.now();
      if (r.ok) setAviso(null);
      else if (r.motivo === "limite") {
        limiteRef.current = true;
        setNoLimite(true);
      } else if (r.motivo === "expirou") irParaLogin();
      // "falha" (API fora do ar): tenta de novo na próxima checagem com uso
    } finally {
      renovando.current = false;
    }
  }, [irParaLogin]);

  const checar = useCallback(() => {
    const agora = Date.now();
    const expiraEm = lerExpiracao(document.cookie, COOKIE_EXPIRA);
    const decisao = decidir({
      agora,
      expiraEm,
      ultimaAtividade: ultimaAtividade.current,
      ultimaRenovacao: ultimaRenovacao.current,
      noLimite: limiteRef.current,
    });
    if (decisao === "sair") irParaLogin();
    else if (decisao === "renovar") void renovar();
    else if (decisao === "avisar" && expiraEm !== null) setAviso(expiraEm - agora);
    else setAviso(null);
  }, [irParaLogin, renovar]);

  useEffect(() => {
    ultimaRenovacao.current = Date.now(); // a página acabou de chegar com a sessão do servidor
    const marcarUso = () => {
      ultimaAtividade.current = Date.now();
    };
    for (const sinal of SINAIS_DE_USO) window.addEventListener(sinal, marcarUso, { passive: true });
    const aoVoltar = () => document.visibilityState === "visible" && checar();
    document.addEventListener("visibilitychange", aoVoltar);
    const relogio = setInterval(checar, INTERVALO_DE_CHECAGEM);
    return () => {
      for (const sinal of SINAIS_DE_USO) window.removeEventListener(sinal, marcarUso);
      document.removeEventListener("visibilitychange", aoVoltar);
      clearInterval(relogio);
    };
  }, [checar]);

  // com o aviso aberto, a contagem anda de segundo em segundo
  useEffect(() => {
    if (aviso === null) return;
    const passo = setInterval(() => {
      const expiraEm = lerExpiracao(document.cookie, COOKIE_EXPIRA);
      if (expiraEm === null) return;
      const resta = expiraEm - Date.now();
      if (resta <= 0) irParaLogin();
      else setAviso(resta);
    }, 1000);
    return () => clearInterval(passo);
  }, [aviso === null, irParaLogin]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Dialog open={aviso !== null} onOpenChange={(aberto) => !aberto && !noLimite && void renovar()}>
      <DialogContent showCloseButton={false} className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Clock className="size-5 text-marca" aria-hidden />
            {noLimite ? "Hora de entrar de novo" : "Sua sessão está quase vencendo"}
          </DialogTitle>
          <DialogDescription>
            {noLimite
              ? "Por segurança, cada login vale por um dia de trabalho. Salve o que estiver fazendo e entre de novo."
              : "Você ficou um tempo sem mexer no sistema. Para continuar de onde parou, é só confirmar."}
          </DialogDescription>
        </DialogHeader>
        <p className="py-2 text-center font-heading text-4xl font-extrabold tabular-nums" aria-live="polite">
          <span className="sr-only">Tempo restante: </span>
          {contagem(aviso ?? 0)}
        </p>
        <DialogFooter>
          <Button variant="ghost" onClick={() => void sair()}>
            Sair agora
          </Button>
          {noLimite ? (
            <Button onClick={irParaLogin}>Entrar de novo</Button>
          ) : (
            <Button onClick={() => void renovar()}>Continuar conectado</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
