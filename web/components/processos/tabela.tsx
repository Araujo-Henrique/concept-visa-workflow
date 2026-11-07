import { Check, Users } from "lucide-react";
import Link from "next/link";

import { SeloConsulado, SeloOrientacao, SeloResultado, SeloSituacao } from "@/components/processos/selos";
import { datasPrincipais, formatarData, formatarDataCurta } from "@/lib/processos";
import type { LinhaPainel, TipoProcesso } from "@/lib/tipos";

/** Tabela de processos (até 50 por página: não precisa de virtualização). A linha inteira abre o processo. */
export function TabelaProcessos({ linhas, tipo }: { linhas: LinhaPainel[]; tipo: TipoProcesso }) {
  if (linhas.length === 0) return <SemResultado />;
  const comConsulado = tipo !== "PASS";
  const comOrientacao = tipo === "OBT";
  const rotulosDatas = datasPrincipais(linhas[0]).map((d) => d.rotulo);

  return (
    <div className="overflow-x-auto rounded-2xl border bg-card">
      <table className="w-full min-w-[860px] text-sm">
        <thead>
          <tr className="border-b text-left text-xs tracking-wide text-muted-foreground uppercase">
            <th className="px-4 py-3 font-medium">Nº</th>
            <th className="px-4 py-3 font-medium">Cliente</th>
            <th className="px-4 py-3 font-medium">Situação</th>
            {comOrientacao && <th className="px-4 py-3 font-medium">Orientação</th>}
            {comConsulado && <th className="px-4 py-3 font-medium">Consulado</th>}
            {rotulosDatas.map((r) => (
              <th key={r} className="px-4 py-3 font-medium">
                {r}
              </th>
            ))}
            <th className="px-4 py-3 font-medium">Resultado</th>
            <th className="px-4 py-3 text-right font-medium">Atualizado</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr
              key={l.processo_id}
              className="group relative border-b transition-colors last:border-0 hover:bg-marca-suave/50"
            >
              <td className="px-4 py-3 font-heading text-xs font-bold tracking-wider text-muted-foreground">
                #{l.processo_id}
              </td>
              <td className="max-w-72 px-4 py-3">
                {/* link "esticado": cobre a linha toda, mas continua um link de verdade (teclado, nova aba) */}
                <Link
                  href={`/processos/${l.processo_id}`}
                  className="block truncate font-medium outline-none after:absolute after:inset-0 focus-visible:after:ring-2 focus-visible:after:ring-ring focus-visible:after:ring-inset"
                >
                  {l.cliente}
                </Link>
                {l.n_solicitantes > 1 && (
                  <span className="mt-0.5 flex items-center gap-1 truncate text-xs text-muted-foreground">
                    <Users className="size-3 shrink-0" /> {l.n_solicitantes} pessoas
                  </span>
                )}
              </td>
              <td className="px-4 py-3">
                <SeloSituacao situacao={l.situacao} />
              </td>
              {comOrientacao && (
                <td className="px-4 py-3">
                  <SeloOrientacao orientacao={l.tipo === "OBT" ? l.orientacao : null} />
                </td>
              )}
              {comConsulado && (
                <td className="px-4 py-3">
                  <SeloConsulado consulado={"consulado" in l ? l.consulado : null} />
                </td>
              )}
              {datasPrincipais(l).map((d) => (
                <td key={d.rotulo} className="px-4 py-3 tabular-nums">
                  {formatarData(d.valor)}
                  {d.rotulo === "Despacho" && l.tipo === "REN" && l.despachado_em && (
                    <Check className="ml-1 inline size-3.5 text-sucesso" aria-label="despachado" />
                  )}
                </td>
              ))}
              <td className="px-4 py-3">
                <SeloResultado resultado={l.resultado_geral} />
              </td>
              <td className="px-4 py-3 text-right text-xs text-muted-foreground tabular-nums">
                {formatarDataCurta(l.atualizado_em)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SemResultado() {
  return (
    <div className="grid place-items-center rounded-2xl border border-dashed bg-card px-6 py-16 text-center">
      <p className="font-heading text-lg font-bold">Nenhum processo por aqui</p>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">
        Nenhum processo combina com esses filtros. Tente limpar algum deles.
      </p>
    </div>
  );
}
