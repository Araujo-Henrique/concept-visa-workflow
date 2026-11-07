"use client";

import { Columns3, Rows3, Search, X } from "lucide-react";
import { useEffect, useState } from "react";

import { useNavegacao } from "@/components/processos/area-processos";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { rotuloSituacao, TIPOS } from "@/lib/formatos";
import {
  DATAS_DO_TIPO,
  DATAS_FILTRAVEIS,
  haFiltros,
  rotuloResultado,
  urlDosFiltros,
  type DataFiltravel,
  type Filtros,
} from "@/lib/processos";
import type { TipoProcesso } from "@/lib/tipos";
import { cn } from "@/lib/utils";

const TODOS = "__todos";
const RESULTADOS = ["Processando", "Aprovado", "Negado", "Parcial"];

type Props = {
  filtros: Filtros;
  situacoes: string[];
  consulados: string[];
  totais: Record<TipoProcesso, number>;
};

export function BarraFiltros({ filtros, situacoes, consulados, totais }: Props) {
  const { navegar } = useNavegacao();
  const [busca, setBusca] = useState(filtros.cliente ?? "");

  // muda um filtro e volta para a página 1 (a página 2 de outro filtro não faz sentido)
  const aplicar = (mudanca: Partial<Filtros>) =>
    navegar(urlDosFiltros({ ...filtros, pagina: 1, ...mudanca }));

  // busca por cliente enquanto digita, sem disparar uma requisição por tecla
  useEffect(() => {
    if (busca === (filtros.cliente ?? "")) return;
    const espera = setTimeout(
      () => navegar(urlDosFiltros({ ...filtros, pagina: 1, cliente: busca || undefined })),
      350,
    );
    return () => clearTimeout(espera);
  }, [busca, filtros, navegar]);

  const datas = DATAS_DO_TIPO[filtros.tipo];
  const dataEscolhida: DataFiltravel = filtros.data ?? datas[0];

  return (
    <div className="mb-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* tipo: como abas de embarque */}
        <nav aria-label="Tipo de processo" className="inline-flex rounded-xl bg-muted p-1">
          {(Object.keys(TIPOS) as TipoProcesso[]).map((tipo) => {
            const atual = tipo === filtros.tipo;
            return (
              <button
                key={tipo}
                type="button"
                aria-current={atual ? "page" : undefined}
                onClick={() => !atual && navegar(urlDosFiltros({ tipo, visao: filtros.visao }))}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors",
                  atual ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                )}
              >
                <span className="font-heading text-[11px] font-bold tracking-widest">{tipo}</span>
                <span className="hidden sm:inline">{TIPOS[tipo].curto}</span>
                <span className="rounded-full bg-background px-1.5 text-[11px] tabular-nums text-muted-foreground">
                  {totais[tipo].toLocaleString("pt-BR")}
                </span>
              </button>
            );
          })}
        </nav>

        <div className="inline-flex rounded-xl bg-muted p-1" role="group" aria-label="Visualização">
          {(
            [
              ["tabela", "Tabela", Rows3],
              ["quadro", "Quadro", Columns3],
            ] as const
          ).map(([visao, rotulo, Icone]) => (
            <button
              key={visao}
              type="button"
              aria-pressed={filtros.visao === visao}
              onClick={() => aplicar({ visao })}
              className={cn(
                "flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                filtros.visao === visao ? "bg-card shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icone className="size-4" /> {rotulo}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-2xl border bg-card p-3">
        <label className="relative min-w-56 flex-1">
          <span className="sr-only">Buscar cliente</span>
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar cliente…"
            className="h-10 pl-9"
          />
        </label>

        {filtros.visao === "tabela" && (
          <Filtro
            rotulo="Situação"
            valor={filtros.situacao}
            opcoes={situacoes.map((s) => [s, rotuloSituacao(s)])}
            aoMudar={(situacao) => aplicar({ situacao })}
          />
        )}
        {filtros.tipo !== "PASS" && (
          <Filtro
            rotulo="Consulado"
            valor={filtros.consulado}
            opcoes={consulados.map((c) => [c, c])}
            aoMudar={(consulado) => aplicar({ consulado })}
          />
        )}
        {filtros.tipo === "REN" && (
          <Filtro
            rotulo="Despacho"
            valor={filtros.despacho}
            opcoes={[
              ["pendente", "A despachar"],
              ["feito", "Despachado"],
            ]}
            aoMudar={(despacho) => aplicar({ despacho: despacho as Filtros["despacho"] })}
          />
        )}
        <Filtro
          rotulo="Resultado"
          valor={filtros.resultado}
          opcoes={RESULTADOS.map((r) => [r, rotuloResultado(r)])}
          aoMudar={(resultado) => aplicar({ resultado })}
        />

        <fieldset className="flex items-end gap-2">
          <legend className="sr-only">Período</legend>
          <Filtro
            rotulo="Período de"
            valor={dataEscolhida}
            semTodos
            opcoes={datas.map((d) => [d, DATAS_FILTRAVEIS[d]])}
            aoMudar={(data) => aplicar({ data: data as DataFiltravel })}
          />
          <CampoData rotulo="De" valor={filtros.de} aoMudar={(de) => aplicar({ data: dataEscolhida, de })} />
          <CampoData
            rotulo="Até"
            valor={filtros.ate}
            aoMudar={(ate) => aplicar({ data: dataEscolhida, ate })}
          />
        </fieldset>

        {haFiltros(filtros) && (
          <button
            type="button"
            onClick={() => {
              setBusca("");
              navegar(urlDosFiltros({ tipo: filtros.tipo, visao: filtros.visao }));
            }}
            className="flex h-10 items-center gap-1 rounded-lg px-3 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="size-4" /> Limpar
          </button>
        )}
      </div>
    </div>
  );
}

function Filtro({
  rotulo,
  valor,
  opcoes,
  aoMudar,
  semTodos = false,
}: {
  rotulo: string;
  valor: string | undefined;
  opcoes: [string, string][];
  aoMudar: (valor: string | undefined) => void;
  semTodos?: boolean;
}) {
  return (
    <div className="space-y-1">
      <span className="block text-xs font-medium text-muted-foreground">{rotulo}</span>
      <Select value={valor ?? TODOS} onValueChange={(v) => aoMudar(v === TODOS ? undefined : v)}>
        <SelectTrigger className="h-10 min-w-36" aria-label={rotulo}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {!semTodos && <SelectItem value={TODOS}>Todos</SelectItem>}
          {opcoes.map(([v, r]) => (
            <SelectItem key={v} value={v}>
              {r}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function CampoData({
  rotulo,
  valor,
  aoMudar,
}: {
  rotulo: string;
  valor: string | undefined;
  aoMudar: (v: string | undefined) => void;
}) {
  return (
    <label className="space-y-1">
      <span className="block text-xs font-medium text-muted-foreground">{rotulo}</span>
      <Input
        type="date"
        value={valor ?? ""}
        onChange={(e) => aoMudar(e.target.value || undefined)}
        className="h-10 w-40"
      />
    </label>
  );
}
