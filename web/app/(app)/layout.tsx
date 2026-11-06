import { Suspense, type ReactNode } from "react";

import { Carregando } from "@/components/movimento/carregando";
import { Estrutura } from "@/components/shell/estrutura";
import { usuarioAtual } from "@/lib/sessao";

/**
 * Área logada: menu lateral + conteúdo. Ler a sessão (cookie) é dado da requisição: com Cache Components
 * isso precisa ficar dentro de um <Suspense>. Quem está logado vem da API, que redireciona ao login se expirou.
 */
async function ComSessao({ children }: { children: ReactNode }) {
  const usuario = await usuarioAtual();
  return <Estrutura usuario={usuario}>{children}</Estrutura>;
}

export default function LayoutApp({ children }: LayoutProps<"/">) {
  return (
    <Suspense fallback={<Carregando texto="Preparando seu painel…" className="min-h-dvh" />}>
      <ComSessao>{children}</ComSessao>
    </Suspense>
  );
}
