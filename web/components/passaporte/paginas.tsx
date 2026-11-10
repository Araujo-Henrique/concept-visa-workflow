"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";

import { Simbolo } from "@/components/marca/simbolo";
import { SeloOrientacao, SeloSituacao } from "@/components/processos/selos";
import { rotuloSituacao, TIPOS } from "@/lib/formatos";
import { formatarTelefone } from "@/lib/formularios";
import { dataEHora, formatarData, inclinacaoDoCarimbo, linhaDeMaquina } from "@/lib/processos";
import type { Evento, LinhaPainel, ProcessoDetalhe } from "@/lib/tipos";
import { cn } from "@/lib/utils";

/** Fundo de "papel de segurança" (guilhoché) das páginas internas. */
export const PAPEL =
  "bg-card [background-image:repeating-radial-gradient(circle_at_100%_0%,color-mix(in_oklab,var(--marca)_7%,transparent)_0_1px,transparent_1px_9px)]";

export function Cabecalho({ titulo, numero, acao }: { titulo: string; numero: number; acao?: ReactNode }) {
  return (
    <header className="mb-6 flex items-center justify-between gap-3 border-b border-dashed pb-3">
      <span className="font-heading text-[10px] font-bold tracking-[0.3em] text-marca-forte uppercase">
        Concept Vistos · {titulo}
      </span>
      <span className="flex items-center gap-3">
        {acao}
        <span className="font-heading text-xs font-bold text-muted-foreground tabular-nums">{numero}</span>
      </span>
    </header>
  );
}

// ---------------------------------------------------------------- capa

export function Capa({ linha }: { linha: LinhaPainel }) {
  return (
    <div className="relative flex h-full min-h-[560px] flex-col items-center justify-between overflow-hidden rounded-2xl bg-tinta px-8 py-12 text-center text-papel shadow-inner">
      <div
        aria-hidden
        className="absolute inset-0 opacity-50 [background-image:radial-gradient(circle_at_50%_35%,rgba(29,157,157,0.25),transparent_60%)]"
      />
      <p className="relative font-heading text-xs font-bold tracking-[0.4em] text-marca">CONCEPT VISTOS</p>
      <div className="relative">
        <Simbolo variante="claro" className="mx-auto h-28 drop-shadow-[0_0_24px_rgba(29,157,157,0.45)]" />
        <p className="mt-8 font-heading text-3xl font-extrabold tracking-[0.25em]">PASSAPORTE</p>
        <p className="mt-1 text-xs tracking-[0.3em] text-papel/60">DO PROCESSO</p>
      </div>
      <div className="relative space-y-1">
        <p className="font-heading text-lg font-bold">{linha.cliente}</p>
        <p className="text-xs tracking-[0.25em] text-papel/60">
          {TIPOS[linha.tipo].nome.toUpperCase()} · Nº {linha.processo_id}
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- dados

type Campo = { rotulo: string; valor: ReactNode; largo?: boolean };

function camposDoTipo(linha: LinhaPainel, d: ProcessoDetalhe): Campo[] {
  const texto = (v: unknown) => (v === null || v === undefined || v === "" ? "—" : String(v));
  const data = (v: unknown) => formatarData(typeof v === "string" ? v : null);
  switch (linha.tipo) {
    case "OBT":
      return [
        { rotulo: "Consulado", valor: texto(d.consulado) },
        { rotulo: "Monitoramento", valor: texto(d.monitoramento) },
        { rotulo: "CASV", valor: data(d.data_casv) },
        { rotulo: "Entrevista", valor: data(d.data_entrevista) },
        { rotulo: "Vencimento da taxa", valor: data(d.data_vencimento_taxa) },
        { rotulo: "Rascunho", valor: texto(d.status_rascunho) },
        {
          rotulo: "Orientação",
          valor: <SeloOrientacao orientacao={typeof d.orientacao === "string" ? d.orientacao : null} />,
        },
        { rotulo: "Data da orientação", valor: data(d.orientacao_data) },
        { rotulo: "Orientado por", valor: texto(linha.orientacao_por) },
        { rotulo: "Rastreio", valor: texto(d.codigo_rastreio) },
      ];
    case "REN":
      return [
        { rotulo: "Consulado", valor: texto(d.consulado) },
        { rotulo: "Documentos", valor: texto(d.docs) },
        { rotulo: "CASV", valor: data(d.data_casv) },
        { rotulo: "Prazo do despacho", valor: data(d.data_despacho) },
        { rotulo: "Rascunho", valor: texto(d.status_rascunho) },
        { rotulo: "Rastreio", valor: texto(d.codigo_rastreio) },
        { rotulo: "Endereço", valor: texto(d.endereco), largo: true },
      ];
    case "PASS":
      return [
        { rotulo: "Polícia Federal", valor: data(d.data_pf) },
        { rotulo: "Prazo", valor: data(d.prazo_pf) },
      ];
  }
}

export function PaginaDados({
  linha,
  emailCliente,
  detalhe,
  acao,
  extra,
}: {
  linha: LinhaPainel;
  emailCliente?: string | null;
  detalhe: ProcessoDetalhe;
  acao?: ReactNode;
  /** faixa abaixo dos campos (o despacho do REN) */
  extra?: ReactNode;
}) {
  const [l1, l2] = linhaDeMaquina(linha.tipo, linha.processo_id, linha.cliente);
  const campos: Campo[] = [
    { rotulo: "Tipo", valor: TIPOS[linha.tipo].nome },
    { rotulo: "Situação", valor: <SeloSituacao situacao={linha.situacao} /> },
    { rotulo: "Cliente", valor: linha.cliente, largo: true },
    {
      rotulo: "E-mail",
      largo: true,
      valor: emailCliente ? (
        // linha inteira: o e-mail não quebra no meio (a equipe copia para entrar no site do consulado)
        <a href={`mailto:${emailCliente}`} className="break-words underline-offset-4 hover:underline">
          {emailCliente}
        </a>
      ) : (
        "—"
      ),
    },
    { rotulo: "Telefone", valor: formatarTelefone(linha.telefone) },
    { rotulo: "Grupo", valor: linha.grupo ?? "—" },
    ...camposDoTipo(linha, detalhe),
    { rotulo: "Aberto em", valor: formatarData(detalhe.criado_em) },
    { rotulo: "Atualizado em", valor: formatarData(detalhe.atualizado_em) },
  ];

  return (
    <div className="flex h-full flex-col">
      <Cabecalho titulo="Dados do processo" numero={2} acao={acao} />
      <div className="relative flex-1">
        <Simbolo
          variante="mono"
          className="pointer-events-none absolute top-0 right-0 h-40 text-marca opacity-[0.07]"
          titulo=""
        />
        <dl className="relative grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
          {campos.map((c) => (
            <div key={c.rotulo} className={cn(c.largo && "col-span-2 sm:col-span-3")}>
              <dt className="text-[10px] font-semibold tracking-[0.15em] text-muted-foreground uppercase">
                {c.rotulo}
              </dt>
              <dd className="mt-0.5 font-medium">{c.valor}</dd>
            </div>
          ))}
        </dl>
        {extra}
        {detalhe.observacao && (
          <div className="mt-6 rounded-xl border border-dashed bg-background/60 p-3">
            <p className="text-[10px] font-semibold tracking-[0.15em] text-muted-foreground uppercase">
              Observação
            </p>
            <p className="mt-1 text-sm whitespace-pre-line">{detalhe.observacao}</p>
          </div>
        )}
      </div>
      {/* "linha de máquina" decorativa, como no pé da página de dados de um passaporte */}
      <div
        aria-hidden
        className="mt-8 overflow-hidden font-mono text-[11px] leading-5 tracking-[0.2em] text-muted-foreground/80 select-none"
      >
        <p className="truncate">{l1}</p>
        <p className="truncate">{l2}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- histórico (carimbos)

const COR_DO_CARIMBO: Record<Evento["tipo"], string> = {
  criado: "text-marca-forte border-marca-forte",
  situacao_alterada: "text-foreground/80 border-foreground/70",
  reaberto: "text-perigo border-perigo",
};

export function PaginaHistorico({ eventos, novo }: { eventos: Evento[]; novo: number | null }) {
  return (
    <div className="flex h-full flex-col">
      <Cabecalho titulo="Carimbos" numero={4} />
      <ol className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3">
        {eventos.map((e) => (
          <Carimbo key={e.id} evento={e} batendo={e.id === novo} />
        ))}
      </ol>
    </div>
  );
}

function Carimbo({ evento, batendo }: { evento: Evento; batendo: boolean }) {
  const titulo = evento.tipo === "criado" ? "Emitido" : evento.tipo === "reaberto" ? "Reaberto" : "Situação";
  const inclinacao = inclinacaoDoCarimbo(evento.id);
  const [data, hora] = dataEHora(evento.criado_em);

  return (
    <li className="flex flex-col items-center text-center">
      <motion.div
        initial={batendo ? { scale: 2.2, opacity: 0, rotate: inclinacao - 20 } : false}
        animate={{ scale: 1, opacity: 1, rotate: inclinacao }}
        transition={{ type: "spring", stiffness: 500, damping: 20 }}
        className={cn(
          "grid size-32 place-items-center rounded-full border-[3px] border-double p-2 mix-blend-multiply dark:mix-blend-normal",
          COR_DO_CARIMBO[evento.tipo],
          batendo && "ring-4 ring-marca/20",
        )}
        aria-label={`${titulo}: ${rotuloSituacao(evento.situacao_nova ?? "")} em ${data}`}
      >
        <div className="font-heading uppercase">
          <p className="text-[9px] font-bold tracking-[0.25em]">{titulo}</p>
          {/* nomes longos (Processando, Pagamento Pendente) diminuem e quebram linha para caber no círculo */}
          <p
            className={cn(
              "mx-auto my-0.5 max-w-[6.25rem] leading-tight font-extrabold break-words",
              rotuloSituacao(evento.situacao_nova ?? "").length > 9 ? "text-[11px]" : "text-sm",
            )}
          >
            {rotuloSituacao(evento.situacao_nova ?? "—")}
          </p>
          <p className="text-[10px] font-bold tabular-nums">{data}</p>
          <p className="text-[9px] tabular-nums opacity-70">{hora}</p>
        </div>
      </motion.div>
      <p className="mt-2 text-xs text-muted-foreground">
        {evento.usuario_nome ? `por ${evento.usuario_nome.split(" ")[0]}` : "importado"}
      </p>
      {evento.motivo && <p className="mt-1 max-w-36 text-xs italic">“{evento.motivo}”</p>}
    </li>
  );
}
