import { History } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { apiLista } from "@/lib/api";
import { type Alteracao, agruparAlteracoes } from "@/lib/auditoria";
import { ErroApi } from "@/lib/erros";
import { dataEHora } from "@/lib/processos";

const LIMITE = 200;

/**
 * "Histórico de alterações" (só admin): quem mudou o quê, com antes e depois, inclusive o que já foi apagado.
 * Componente do servidor; fica fechado (<details>) para não pesar a página. A página só o inclui para admin,
 * e a API confere de novo (403 para os demais).
 */
export async function HistoricoAlteracoes({
  filtro,
}: {
  filtro: { cliente_id: number } | { processo_id: number };
}) {
  let itens: Alteracao[];
  let total: number | null;
  try {
    ({ itens, total } = await apiLista<Alteracao>("/auditoria", { ...filtro, limit: LIMITE }));
  } catch (erro) {
    if (!(erro instanceof ErroApi)) throw erro; // redirect de sessão expirada segue o fluxo do Next
    return (
      <Moldura quantidade={null}>
        <p role="alert" className="text-sm text-destructive">
          Não consegui carregar o histórico agora. {erro.message}
        </p>
      </Moldura>
    );
  }
  const grupos = agruparAlteracoes(itens);

  return (
    <Moldura quantidade={total ?? itens.length}>
      {grupos.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhuma alteração registrada desde que a auditoria foi ligada.
        </p>
      ) : (
        <ol className="relative space-y-6 border-l border-dashed pl-5">
          {grupos.map((g) => {
            const [dia, hora] = dataEHora(g.criado_em);
            return (
              <li key={g.transacao} className="relative">
                <span className="absolute top-1.5 -left-[25px] size-2.5 rounded-full bg-marca ring-4 ring-background" />
                <p className="text-xs text-muted-foreground">
                  {dia} às {hora} · por <span className="font-medium text-foreground">{g.autor}</span>
                  {g.requisicao && <span className="font-mono"> · código {g.requisicao}</span>}
                </p>
                <ul className="mt-2 space-y-3">
                  {g.itens.map((item) => (
                    <li key={item.id}>
                      <p className="text-sm font-medium">{item.titulo}</p>
                      {item.campos.length > 0 && (
                        <dl className="mt-1 grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-sm">
                          {item.campos.map((c) => (
                            <div key={c.rotulo} className="contents">
                              <dt className="text-muted-foreground">{c.rotulo}</dt>
                              <dd className="break-words">
                                {c.depois === null ? (
                                  c.antes
                                ) : (
                                  <>
                                    <span className="text-muted-foreground line-through">{c.antes}</span>
                                    {" → "}
                                    <span>{c.depois}</span>
                                  </>
                                )}
                              </dd>
                            </div>
                          ))}
                        </dl>
                      )}
                    </li>
                  ))}
                </ul>
              </li>
            );
          })}
        </ol>
      )}
      {total !== null && total > itens.length && (
        <p className="mt-4 text-xs text-muted-foreground">
          Mostrando as {itens.length} alterações mais recentes de {total}.
        </p>
      )}
    </Moldura>
  );
}

function Moldura({ quantidade, children }: { quantidade: number | null; children: React.ReactNode }) {
  return (
    <section aria-label="Histórico de alterações" className="mt-10">
      <details className="rounded-2xl border bg-card">
        <summary className="flex cursor-pointer items-center gap-2 px-5 py-4 font-heading text-sm font-bold tracking-wider uppercase">
          <History className="size-4 text-marca" /> Histórico de alterações
          {quantidade !== null && ` · ${quantidade}`}
          <span className="ml-auto text-xs font-normal tracking-normal text-muted-foreground normal-case">
            visível só para administradores
          </span>
        </summary>
        <div className="border-t px-5 py-5">{children}</div>
      </details>
    </section>
  );
}

export function EsqueletoHistorico() {
  return <Skeleton aria-hidden className="mt-10 h-14 rounded-2xl" />;
}
