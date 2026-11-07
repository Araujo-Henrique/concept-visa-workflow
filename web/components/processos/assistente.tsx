"use client";

import { ArrowLeft, ArrowRight, Check, Plane, Plus, Search, Stamp, UserPlus, Users, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { buscarClientes } from "@/app/acoes/clientes";
import { criarProcesso } from "@/app/acoes/processos";
import { FormCliente } from "@/components/clientes/form-cliente";
import { CampoSelecao } from "@/components/formularios/campos";
import { FormDados } from "@/components/processos/form-dados";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { rotuloSituacao, TIPOS } from "@/lib/formatos";
import {
  corpoProcessoNovo,
  formatarTelefone,
  validarProcesso,
  valoresIniciais,
  type Erros,
  type Valores,
} from "@/lib/formularios";
import { formatarData } from "@/lib/processos";
import type { Cliente, ClienteLista, Referencias, TipoProcesso } from "@/lib/tipos";
import { cn } from "@/lib/utils";

const ETAPAS = ["Cliente", "Tipo", "Dados", "Pessoas", "Embarque"] as const;

const DESCRICAO_DO_TIPO: Record<TipoProcesso, string> = {
  OBT: "Primeiro visto americano (B1/B2, F1…): DS-160, CASV, entrevista e orientação.",
  REN: "Renovação do visto: documentos, CASV e despacho pelo correio.",
  PASS: "Passaporte brasileiro: agendamento e prazo na Polícia Federal.",
};

/** Situação com que o processo nasce (dá para trocar no passo Dados). */
export function situacaoInicial(tipo: TipoProcesso, situacoes: string[]): string {
  const preferida = tipo === "PASS" ? "Pendente" : "Cadastro";
  return situacoes.includes(preferida) ? preferida : situacoes[0];
}

export function Assistente({
  referencias,
  clienteInicial,
}: {
  referencias: Referencias;
  clienteInicial: Cliente | null;
}) {
  const router = useRouter();
  const [etapa, setEtapa] = useState(clienteInicial ? 1 : 0);
  const [cliente, setCliente] = useState<Cliente | null>(clienteInicial);
  const [tipo, setTipo] = useState<TipoProcesso | null>(null);
  const [situacao, setSituacao] = useState("");
  const [valores, setValores] = useState<Valores>({});
  const [erros, setErros] = useState<Erros>({});
  const [extras, setExtras] = useState<string[]>([]);
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [emitido, setEmitido] = useState<number | null>(null);
  const [emitindo, iniciar] = useTransition();

  const escolherTipo = (t: TipoProcesso) => {
    if (t !== tipo) {
      setTipo(t);
      setValores(valoresIniciais(t));
      setSituacao(situacaoInicial(t, referencias.situacoes[t]));
      setErros({});
    }
    setEtapa(2);
  };

  const avancarDados = () => {
    if (!tipo) return;
    const encontrados = validarProcesso(tipo, valores);
    setErros(encontrados);
    if (Object.keys(encontrados).length === 0) setEtapa(3);
  };

  const emitir = () => {
    if (!cliente || !tipo) return;
    setErroGeral(null);
    iniciar(async () => {
      const r = await criarProcesso(tipo, corpoProcessoNovo(tipo, cliente.id, situacao, valores, extras));
      if (!r.ok) {
        setErroGeral(r.erro);
        return;
      }
      setEmitido(r.dados.id);
      setTimeout(() => router.push(`/processos/${r.dados.id}`), 1300); // tempo do carimbo "emitido"
    });
  };

  const podeIrPara = (i: number) => i < etapa && !emitido; // volta para qualquer parada já feita

  return (
    <div className="mx-auto max-w-3xl">
      {/* a rota: cada passo é uma parada; o avião fica no passo atual */}
      <ol className="mb-8 flex items-center" aria-label="Etapas">
        {ETAPAS.map((nome, i) => (
          <li key={nome} className={cn("flex items-center", i < ETAPAS.length - 1 && "flex-1")}>
            <button
              type="button"
              disabled={!podeIrPara(i)}
              onClick={() => setEtapa(i)}
              aria-current={i === etapa ? "step" : undefined}
              className="flex flex-col items-center gap-1.5 disabled:cursor-default"
            >
              <span
                className={cn(
                  "grid size-9 place-items-center rounded-full border-2 bg-card text-xs font-bold transition-colors",
                  i < etapa && "border-marca-forte/60 text-marca-forte",
                  i === etapa && "border-marca bg-marca text-tinta",
                )}
              >
                {i < etapa ? (
                  <Check className="size-4" />
                ) : i === etapa ? (
                  <Plane className="size-4" />
                ) : (
                  i + 1
                )}
              </span>
              <span className={cn("text-xs", i === etapa ? "font-semibold" : "text-muted-foreground")}>
                {nome}
              </span>
            </button>
            {i < ETAPAS.length - 1 && (
              <span
                aria-hidden
                className={cn(
                  "mx-2 mb-5 h-0.5 flex-1 rounded-full",
                  i < etapa
                    ? "bg-marca"
                    : "bg-[repeating-linear-gradient(to_right,var(--border)_0_6px,transparent_6px_10px)]",
                )}
              />
            )}
          </li>
        ))}
      </ol>

      <div className="rounded-2xl border bg-card p-6 sm:p-8">
        {etapa === 0 && (
          <PassoCliente
            aoEscolher={(c) => {
              setCliente(c);
              setEtapa(1);
            }}
          />
        )}

        {etapa === 1 && (
          <section>
            <Titulo titulo="Qual é o tipo de processo?" subtitulo={`Para ${cliente?.nome}.`} />
            <div className="grid gap-3 sm:grid-cols-3">
              {(Object.keys(TIPOS) as TipoProcesso[]).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => escolherTipo(t)}
                  className={cn(
                    "group overflow-hidden rounded-xl border text-left transition-all hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                    tipo === t && "ring-2 ring-marca",
                  )}
                >
                  <div className="flex items-center justify-between bg-tinta px-4 py-3 text-papel">
                    <span className="font-heading text-sm font-extrabold tracking-[0.25em]">{t}</span>
                    <Plane className="size-4 text-marca transition-transform group-hover:translate-x-1" />
                  </div>
                  <div className="p-4">
                    <p className="font-heading font-bold">{TIPOS[t].nome}</p>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      {DESCRICAO_DO_TIPO[t]}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </section>
        )}

        {etapa === 2 && tipo && (
          <section>
            <Titulo
              titulo="Dados do processo"
              subtitulo="Só o que já se sabe; o resto dá para completar depois."
            />
            <div className="mb-6 max-w-xs">
              <CampoSelecao
                rotulo="Situação inicial"
                valor={situacao}
                aoMudar={setSituacao}
                opcoes={referencias.situacoes[tipo].map((s) => [s, rotuloSituacao(s)])}
              />
            </div>
            <FormDados
              tipo={tipo}
              valores={valores}
              erros={erros}
              referencias={referencias}
              aoMudar={(campo, valor) => setValores((v) => ({ ...v, [campo]: valor }))}
            />
            <Navegacao voltar={() => setEtapa(1)} avancar={avancarDados} />
          </section>
        )}

        {etapa === 3 && cliente && (
          <section>
            <Titulo
              titulo="Quem vai viajar?"
              subtitulo="O titular é o cliente. Acrescente as outras pessoas do grupo."
            />
            <PassoPessoas titular={cliente.nome} extras={extras} aoMudar={setExtras} />
            <Navegacao voltar={() => setEtapa(2)} avancar={() => setEtapa(4)} />
          </section>
        )}

        {etapa === 4 && cliente && tipo && (
          <section className="relative">
            <Titulo titulo="Tudo pronto para o embarque" subtitulo="Confira o cartão e emita o processo." />
            <CartaoEmbarque
              cliente={cliente}
              tipo={tipo}
              situacao={situacao}
              valores={valores}
              extras={extras}
            />
            {erroGeral && (
              <p role="alert" className="mt-4 rounded-lg bg-perigo-suave px-3 py-2 text-sm text-perigo">
                {erroGeral}
              </p>
            )}
            <div className="mt-6 flex justify-between">
              <Button variant="ghost" onClick={() => setEtapa(3)} disabled={emitindo || Boolean(emitido)}>
                <ArrowLeft className="size-4" /> Voltar
              </Button>
              <Button onClick={emitir} disabled={emitindo || Boolean(emitido)} className="h-11 px-6">
                <Stamp className="size-4" /> {emitindo ? "Emitindo…" : "Emitir processo"}
              </Button>
            </div>
            <AnimatePresence>{emitido && <CarimboEmitido numero={emitido} />}</AnimatePresence>
          </section>
        )}
      </div>
    </div>
  );
}

function Titulo({ titulo, subtitulo }: { titulo: string; subtitulo: string }) {
  return (
    <header className="mb-6">
      <h2 className="text-xl font-extrabold">{titulo}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{subtitulo}</p>
    </header>
  );
}

function Navegacao({ voltar, avancar }: { voltar: () => void; avancar: () => void }) {
  return (
    <div className="mt-8 flex justify-between">
      <Button variant="ghost" onClick={voltar}>
        <ArrowLeft className="size-4" /> Voltar
      </Button>
      <Button onClick={avancar}>
        Continuar <ArrowRight className="size-4" />
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------- passo 1: cliente

function PassoCliente({ aoEscolher }: { aoEscolher: (c: Cliente) => void }) {
  const [termo, setTermo] = useState("");
  const [resultados, setResultados] = useState<ClienteLista[]>([]);
  const [cadastrando, setCadastrando] = useState(false);
  const [buscando, iniciar] = useTransition();

  useEffect(() => {
    const espera = setTimeout(() => iniciar(async () => setResultados(await buscarClientes(termo))), 250);
    return () => clearTimeout(espera);
  }, [termo]);

  if (cadastrando)
    return (
      <section>
        <Titulo titulo="Novo cliente" subtitulo="Cadastre e siga direto para o processo." />
        <FormCliente nomeInicial={termo} aoSalvar={aoEscolher} aoCancelar={() => setCadastrando(false)} />
      </section>
    );

  return (
    <section>
      <Titulo titulo="Para qual cliente?" subtitulo="Busque pelo nome, e-mail ou telefone." />
      <label className="relative block">
        <span className="sr-only">Buscar cliente</span>
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          autoFocus
          value={termo}
          onChange={(e) => setTermo(e.target.value)}
          placeholder="Ex.: Souza ou 41 99999"
          className="h-11 pl-9"
        />
      </label>

      <ul className="mt-4 space-y-2" aria-busy={buscando}>
        {resultados.map((c) => (
          <li key={c.id}>
            <button
              type="button"
              onClick={() => aoEscolher(c)}
              className="flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition-colors hover:border-marca hover:bg-marca-suave/50"
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{c.nome}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {[c.telefone && formatarTelefone(c.telefone), c.email].filter(Boolean).join(" · ") ||
                    "sem contato"}
                </span>
              </span>
              <span className="text-xs text-muted-foreground">
                {c.n_processos} {c.n_processos === 1 ? "processo" : "processos"}
              </span>
              <ArrowRight className="size-4 text-muted-foreground" />
            </button>
          </li>
        ))}
      </ul>

      {termo.trim().length >= 2 && !buscando && resultados.length === 0 && (
        <p className="mt-4 text-sm text-muted-foreground">Nenhum cliente com “{termo.trim()}”.</p>
      )}
      <Button variant="outline" onClick={() => setCadastrando(true)} className="mt-4">
        <UserPlus className="size-4" /> Cadastrar cliente novo
        {termo.trim() && <span className="max-w-48 truncate text-muted-foreground">“{termo.trim()}”</span>}
      </Button>
    </section>
  );
}

// ---------------------------------------------------------------- passo 4: pessoas

function PassoPessoas({
  titular,
  extras,
  aoMudar,
}: {
  titular: string;
  extras: string[];
  aoMudar: (e: string[]) => void;
}) {
  const [nome, setNome] = useState("");
  const adicionar = () => {
    if (!nome.trim()) return;
    aoMudar([...extras, nome.trim()]);
    setNome("");
  };
  return (
    <div>
      <ul className="space-y-2">
        <li className="flex items-center gap-3 rounded-xl border bg-marca-suave/40 px-4 py-3">
          <span className="font-medium">{titular}</span>
          <span className="text-[10px] font-semibold tracking-[0.2em] text-marca-forte uppercase">
            Titular
          </span>
        </li>
        {extras.map((e, i) => (
          <li key={`${e}-${i}`} className="flex items-center gap-3 rounded-xl border px-4 py-3">
            <span className="flex-1">{e}</span>
            <button
              type="button"
              onClick={() => aoMudar(extras.filter((_, j) => j !== i))}
              className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label={`Tirar ${e}`}
            >
              <X className="size-4" />
            </button>
          </li>
        ))}
      </ul>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(ev) => {
          ev.preventDefault();
          adicionar();
        }}
      >
        <Input
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          placeholder="Nome de mais uma pessoa"
          className="h-10"
          aria-label="Nome da pessoa"
        />
        <Button type="submit" variant="outline" disabled={!nome.trim()}>
          <Plus className="size-4" /> Incluir
        </Button>
      </form>
      <p className="mt-2 text-xs text-muted-foreground">
        Os códigos DS-160 de cada pessoa entram depois, no passaporte do processo.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------- passo 5: cartão de embarque

function CartaoEmbarque({
  cliente,
  tipo,
  situacao,
  valores,
  extras,
}: {
  cliente: Cliente;
  tipo: TipoProcesso;
  situacao: string;
  valores: Valores;
  extras: string[];
}) {
  const linhas: [string, string][] = [
    ["Situação", rotuloSituacao(situacao)],
    ...(tipo !== "PASS" ? ([["Consulado", valores.consulado || "—"]] as [string, string][]) : []),
    ...(tipo === "OBT"
      ? ([
          ["CASV", formatarData(valores.data_casv)],
          ["Entrevista", formatarData(valores.data_entrevista)],
        ] as [string, string][])
      : []),
    ...(tipo === "REN" ? ([["CASV", formatarData(valores.data_casv)]] as [string, string][]) : []),
    ...(tipo === "PASS"
      ? ([
          ["PF", formatarData(valores.data_pf)],
          ["Prazo", formatarData(valores.prazo_pf)],
        ] as [string, string][])
      : []),
  ];
  return (
    <article className="flex overflow-hidden rounded-2xl border shadow-sm">
      <div className="flex-1 p-5">
        <div className="flex items-center justify-between">
          <p className="font-heading text-[10px] font-bold tracking-[0.3em] text-marca-forte">
            CARTÃO DE EMBARQUE
          </p>
          <p className="font-heading text-xs font-bold tracking-widest text-muted-foreground">{tipo}</p>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">Passageiro</p>
        <p className="font-heading text-xl font-extrabold">{cliente.nome}</p>
        <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {linhas.map(([r, v]) => (
            <div key={r}>
              <dt className="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase">
                {r}
              </dt>
              <dd className="font-medium tabular-nums">{v}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-4 flex items-center gap-1.5 text-sm text-muted-foreground">
          <Users className="size-4" /> {1 + extras.length} {extras.length ? "pessoas" : "pessoa"}
          {extras.length > 0 && `: ${[cliente.nome.split(" ")[0], ...extras].join(", ")}`}
        </p>
      </div>
      {/* canhoto */}
      <div className="hidden w-36 flex-col items-center justify-center gap-2 border-l-2 border-dashed bg-tinta p-4 text-papel sm:flex">
        <Plane className="size-6 text-marca" />
        <span className="font-heading text-2xl font-extrabold tracking-widest">{tipo}</span>
        <span className="text-[10px] tracking-[0.2em] text-papel/60">{TIPOS[tipo].curto.toUpperCase()}</span>
      </div>
    </article>
  );
}

function CarimboEmitido({ numero }: { numero: number }) {
  return (
    <motion.div
      role="status"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="pointer-events-none absolute inset-0 grid place-items-center bg-card/70 backdrop-blur-[1px]"
    >
      <motion.div
        initial={{ scale: 2.4, rotate: -24, opacity: 0 }}
        animate={{ scale: 1, rotate: -10, opacity: 1 }}
        transition={{ type: "spring", stiffness: 520, damping: 22 }}
        className="grid size-44 place-items-center rounded-full border-[5px] border-double border-marca-forte text-center text-marca-forte"
      >
        <div className="font-heading uppercase">
          <p className="text-[10px] font-bold tracking-[0.3em]">Concept Vistos</p>
          <p className="my-1 text-2xl font-extrabold leading-none">Emitido</p>
          <p className="text-sm font-bold">Nº {numero}</p>
        </div>
      </motion.div>
    </motion.div>
  );
}
