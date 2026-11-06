"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useTransition, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Os filtros moram na URL (dá para copiar o link e mandar para um colega). Trocar um filtro troca a URL
 * dentro de uma transição: a lista antiga continua na tela, levemente apagada, até a nova chegar.
 */
type Navegacao = { navegar: (url: string) => void; carregando: boolean };
const Contexto = createContext<Navegacao>({ navegar: () => {}, carregando: false });

export const useNavegacao = () => useContext(Contexto);

export function AreaProcessos({ barra, children }: { barra: ReactNode; children: ReactNode }) {
  const router = useRouter();
  const [carregando, iniciar] = useTransition();
  const navegar = useCallback(
    (url: string) => iniciar(() => router.replace(url, { scroll: false })),
    [router],
  );

  return (
    <Contexto.Provider value={{ navegar, carregando }}>
      {barra}
      <div
        aria-busy={carregando}
        className={cn("transition-opacity duration-200", carregando && "pointer-events-none opacity-55")}
      >
        {children}
      </div>
    </Contexto.Provider>
  );
}
