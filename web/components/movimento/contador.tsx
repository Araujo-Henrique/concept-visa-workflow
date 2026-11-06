"use client";

import { animate, useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { useMovimento } from "@/components/provedores";

const formato = new Intl.NumberFormat("pt-BR");

/** Número que "sobe" até o valor quando aparece na tela (como os contadores do site). */
export function Contador({
  valor,
  duracao = 1.2,
  className,
}: {
  valor: number;
  duracao?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const visivel = useInView(ref, { once: true });
  const { reduzido: parado } = useMovimento(); // já inclui o sistema, sem quebrar a hidratação
  const [animado, setAnimado] = useState(0);
  const atual = parado ? valor : animado; // sem animação, mostra o valor direto

  useEffect(() => {
    if (!visivel || parado) return;
    const controle = animate(0, valor, {
      duration: duracao,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => setAnimado(Math.round(v)),
    });
    return () => controle.stop();
  }, [visivel, valor, duracao, parado]);

  return (
    <span ref={ref} className={className} aria-label={formato.format(valor)}>
      <span aria-hidden>{formato.format(atual)}</span>
    </span>
  );
}
