import { Check, Users } from "lucide-react";
import Link from "next/link";

import {
  SeloConsulado,
  SeloDs160,
  SeloOrientacao,
  SeloResultado,
  SeloSituacao,
} from "@/components/processos/selos";
import {
  datasPrincipais,
  formatarData,
  formatarDataCurta,
  ROTULO_PREVISAO_ORIENTACAO,
} from "@/lib/processos";
import type { LinhaPainel, TipoProcesso } from "@/lib/tipos";

/** Tabela de processos (até 50 por página: não precisa de virtualização). A linha inteira abre o processo. */
export function TabelaProcessos({ linhas, tipo }: { linhas: LinhaPainel[]; tipo: TipoProcesso }) {
  if (linhas.length === 0) return <SemResultado />;
  const comConsulado = tipo !== "PASS";
  const comOrientacao = tipo === "OBT";
  const comDs160 = tipo !== "PASS"; // passaporte não tem DS-160
  const rotulosDatas = datasPrincipais(linhas[0]).map((d) => d.rotulo);

  return (
    <div className="overflow-x-auto rounded-2xl border bg-card">
      <table className="w-full min-w-[980px] text-sm">
        <thead>
          <tr className="border-b text-left text-xs tracking-wide text-muted-foreground uppercase">
            <th className="px-3 py-3 font-medium">Nº</th>
            <th className="px-3 py-3 font-medium">Cliente</th>
            <th className="px-3 py-3 font-medium">Situação</th>
            {comOrientacao && <th className="px-3 py-3 font-medium">Orientação</th>}
            {comDs160 && <th className="px-3 py-3 font-medium">DS-160</th>}
            {comConsulado && <th className="px-3 py-3 font-medium">Consulado</th>}
            {rotulosDatas.map((r) => (
              <th key={r} className="px-3 py-3 font-medium">
                {r}
              </th>
            ))}
            <th className="px-3 py-3 font-medium">Resultado</th>
            <th className="px-3 py-3 text-right font-medium">Atualizado</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr
              key={l.processo_id}
              className="group relative border-b transition-colors last:border-0 hover:bg-marca-suave/50"
            >
              <td className="px-3 py-3 font-heading text-xs font-bold tracking-wider text-muted-foreground">
                #{l.processo_id}
              </td>
              <td className="max-w-72 px-3 py-3">
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
              <td className="px-3 py-3">
                <SeloSituacao situacao={l.situacao} />
              </td>
              {comOrientacao && (
                <td className="px-3 py-3">
                  <SeloOrientacao orientacao={l.tipo === "OBT" ? l.orientacao : null} />
                  {/* a data da orientação agendada também conta na ordem da tabela: precisa estar à vista */}
                  {l.tipo === "OBT" && l.orientacao === "Agendada" && l.orientacao_data && (
                    <span className="mt-0.5 block text-[11px] text-muted-foreground tabular-nums">
                      {formatarData(l.orientacao_data)}
                    </span>
                  )}
                </td>
              )}
              {comDs160 && (
                <td className="px-3 py-3">
                  {l.tipo !== "PASS" && (
                    <SeloDs160
                      status={l.ds160_status}
                      fechados={l.ds160_fechados}
                      formularios={l.n_formularios}
                      pessoas={l.n_solicitantes}
                    />
                  )}
                </td>
              )}
              {comConsulado && (
                <td className="px-3 py-3">
                  <SeloConsulado consulado={"consulado" in l ? l.consulado : null} />
                </td>
              )}
              {datasPrincipais(l).map((d) => (
                <td key={d.rotulo} className="px-3 py-3 tabular-nums">
                  {formatarData(d.valor)}
                  {d.rotulo === "Despacho" && l.tipo === "REN" && l.despachado_em && (
                    <Check className="ml-1 inline size-3.5 text-sucesso" aria-label="despachado" />
                  )}
                  {/* a previsão é só uma conta; o ✓ aparece quando a orientação já foi dada */}
                  {d.rotulo === ROTULO_PREVISAO_ORIENTACAO &&
                    l.tipo === "OBT" &&
                    l.orientacao === "Fornecidas" && (
                      <Check
                        className="ml-1 inline size-3.5 text-sucesso"
                        aria-label="orientação fornecida"
                      />
                    )}
                </td>
              ))}
              <td className="px-3 py-3">
                <SeloResultado resultado={l.resultado_geral} />
              </td>
              <td className="px-3 py-3 text-right text-xs text-muted-foreground tabular-nums">
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
