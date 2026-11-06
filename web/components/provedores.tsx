"use client";

import { MotionConfig } from "motion/react";
import { ThemeProvider } from "next-themes";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { CHAVE_MOVIMENTO } from "@/lib/constantes";
import { animacoesReduzidas, lerValor, type PreferenciaMovimento } from "@/lib/movimento";

type Movimento = {
  /** animações decorativas devem ficar paradas */
  reduzido: boolean;
  preferencia: PreferenciaMovimento;
  /** o sistema operacional pede menos movimento */
  sistemaReduz: boolean;
  definir: (preferencia: PreferenciaMovimento) => void;
};

const ContextoMovimento = createContext<Movimento>({
  reduzido: false,
  preferencia: "sistema",
  sistemaReduz: false,
  definir: () => {},
});

export function useMovimento() {
  return useContext(ContextoMovimento);
}

/*
 * Preferência (localStorage) e "reduzir movimento" do sistema moram fora do React: lidos com
 * useSyncExternalStore. No servidor, e na hidratação, o valor é sempre o mesmo ("sistema", sem redução);
 * o navegador só aplica o valor real logo depois. Assim o HTML do servidor e o primeiro desenho do
 * navegador são idênticos (sem erro de hidratação).
 */
const EVENTO = "cv-movimento-mudou";
const CONSULTA = "(prefers-reduced-motion: reduce)";

function lerPreferencia(): PreferenciaMovimento {
  try {
    return lerValor(localStorage.getItem(CHAVE_MOVIMENTO));
  } catch {
    return "sistema"; // navegação privada ou armazenamento bloqueado
  }
}

function assinarPreferencia(aoMudar: () => void) {
  window.addEventListener("storage", aoMudar); // outra aba mudou
  window.addEventListener(EVENTO, aoMudar); // esta aba mudou
  return () => {
    window.removeEventListener("storage", aoMudar);
    window.removeEventListener(EVENTO, aoMudar);
  };
}

function assinarSistema(aoMudar: () => void) {
  const consulta = window.matchMedia(CONSULTA);
  consulta.addEventListener("change", aoMudar);
  return () => consulta.removeEventListener("change", aoMudar);
}

export function Provedores({ children }: { children: ReactNode }) {
  const preferencia = useSyncExternalStore(assinarPreferencia, lerPreferencia, () => "sistema" as const);
  const sistemaReduz = useSyncExternalStore(
    assinarSistema,
    () => window.matchMedia(CONSULTA).matches,
    () => false,
  );
  const reduzido = animacoesReduzidas(preferencia, sistemaReduz);

  useEffect(() => {
    // o CSS global usa este atributo para parar (ou liberar) as animações feitas só com CSS
    document.documentElement.dataset.movimento = reduzido ? "reduzido" : "normal";
  }, [reduzido]);

  const definir = useCallback((nova: PreferenciaMovimento) => {
    try {
      localStorage.setItem(CHAVE_MOVIMENTO, nova);
    } catch {
      /* sem armazenamento: não há onde guardar a preferência */
    }
    window.dispatchEvent(new Event(EVENTO));
  }, []);

  return (
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem disableTransitionOnChange>
      <ContextoMovimento.Provider value={{ reduzido, preferencia, sistemaReduz, definir }}>
        {/* a decisão já foi tomada acima (inclui o sistema), então o motion obedece a ela, não ao sistema */}
        <MotionConfig reducedMotion={reduzido ? "always" : "never"}>
          <TooltipProvider delayDuration={300}>
            {children}
            <Toaster richColors position="top-right" />
          </TooltipProvider>
        </MotionConfig>
      </ContextoMovimento.Provider>
    </ThemeProvider>
  );
}
