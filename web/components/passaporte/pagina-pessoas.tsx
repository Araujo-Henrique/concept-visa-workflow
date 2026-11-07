"use client";

import { Crown, Plus, Trash2, UserPlus } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import {
  adicionarFormulario,
  adicionarSolicitante,
  mudarResultado,
  mudarStatusFormulario,
  removerFormulario,
  removerSolicitante,
  tornarTitular,
} from "@/app/acoes/processos";
import { Cabecalho } from "@/components/passaporte/paginas";
import { SeloResultado } from "@/components/processos/selos";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { normalizarCodigo, PADRAO_DS160 } from "@/lib/formularios";
import { rotuloResultado } from "@/lib/processos";
import type { Formulario, Solicitante } from "@/lib/tipos";

type Permissoes = { escrever: boolean; apagar: boolean };

/** Executa uma ação da API com aviso de sucesso ou erro (a tela relê os dados sozinha quando dá certo). */
function useAcao() {
  const [ocupado, iniciar] = useTransition();
  const executar = (acao: () => Promise<{ ok: boolean; erro?: string }>, sucesso: string) =>
    iniciar(async () => {
      const r = await acao();
      if (r.ok) toast.success(sucesso);
      else toast.error("Não deu certo", { description: (r as { erro: string }).erro });
    });
  return { ocupado, executar };
}

export function PaginaPessoas({
  processoId,
  solicitantes,
  comDs160,
  statusDs,
  permissoes,
}: {
  processoId: number;
  solicitantes: Solicitante[];
  comDs160: boolean;
  statusDs: string[];
  permissoes: Permissoes;
}) {
  const { ocupado, executar } = useAcao();
  const [nome, setNome] = useState("");

  return (
    <div className="flex h-full flex-col">
      <Cabecalho titulo={comDs160 ? "Solicitantes e DS-160" : "Solicitantes"} numero={3} />
      <ul className="space-y-3">
        {solicitantes.map((s) => (
          <Pessoa key={s.id} s={s} comDs160={comDs160} statusDs={statusDs} permissoes={permissoes} />
        ))}
      </ul>

      {permissoes.escrever && (
        <form
          className="mt-4 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!nome.trim()) return;
            executar(() => adicionarSolicitante(processoId, nome.trim()), `${nome.trim()} incluído(a)`);
            setNome("");
          }}
        >
          <Input
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Incluir mais uma pessoa no processo"
            aria-label="Nome da pessoa"
            className="h-9 bg-background/70"
          />
          <Button
            type="submit"
            variant="outline"
            size="sm"
            disabled={!nome.trim() || ocupado}
            className="h-9"
          >
            <UserPlus className="size-4" /> Incluir
          </Button>
        </form>
      )}
    </div>
  );
}

function Pessoa({
  s,
  comDs160,
  statusDs,
  permissoes,
}: {
  s: Solicitante;
  comDs160: boolean;
  statusDs: string[];
  permissoes: Permissoes;
}) {
  const { ocupado, executar } = useAcao();
  const primeiro = s.nome.split(" ")[0];

  return (
    <li className="rounded-xl border bg-background/70 p-4" aria-busy={ocupado}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-heading font-bold">{s.nome}</p>
          {s.titular ? (
            <span className="text-[10px] font-semibold tracking-[0.2em] text-marca-forte uppercase">
              Titular
            </span>
          ) : (
            permissoes.escrever && (
              <button
                type="button"
                disabled={ocupado}
                onClick={() => executar(() => tornarTitular(s.id), `${primeiro} agora é o titular`)}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              >
                <Crown className="size-3" /> Tornar titular
              </button>
            )
          )}
        </div>
        <div className="flex items-center gap-2">
          {permissoes.escrever ? (
            <Select
              value={s.resultado}
              disabled={ocupado}
              onValueChange={(resultado) =>
                executar(() => mudarResultado(s.id, resultado), `${primeiro}: ${rotuloResultado(resultado)}`)
              }
            >
              <SelectTrigger className="h-8 w-36" aria-label={`Resultado de ${s.nome}`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["Processando", "Aprovado", "Negado"].map((r) => (
                  <SelectItem key={r} value={r}>
                    {rotuloResultado(r)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <SeloResultado resultado={s.resultado} />
          )}
          {permissoes.apagar && !s.titular && (
            <button
              type="button"
              disabled={ocupado}
              onClick={() => {
                if (confirm(`Tirar ${s.nome} do processo? Os formulários DS-160 dele(a) saem junto.`))
                  executar(() => removerSolicitante(s.id), `${primeiro} saiu do processo`);
              }}
              className="rounded p-1.5 text-muted-foreground hover:bg-perigo-suave hover:text-perigo"
              aria-label={`Tirar ${s.nome} do processo`}
            >
              <Trash2 className="size-4" />
            </button>
          )}
        </div>
      </div>

      {comDs160 && (
        <div className="mt-3">
          <ul className="flex flex-wrap gap-2">
            {s.formularios.length === 0 && (
              <li className="text-xs text-muted-foreground">Nenhum formulário DS-160.</li>
            )}
            {s.formularios.map((f) => (
              <CodigoDs160 key={f.id} f={f} statusDs={statusDs} permissoes={permissoes} />
            ))}
          </ul>
          {permissoes.escrever && <NovoCodigo solicitanteId={s.id} statusDs={statusDs} />}
        </div>
      )}
    </li>
  );
}

function CodigoDs160({
  f,
  statusDs,
  permissoes,
}: {
  f: Formulario;
  statusDs: string[];
  permissoes: Permissoes;
}) {
  const { ocupado, executar } = useAcao();
  return (
    <li
      title={f.observacao ?? undefined}
      className="flex items-center gap-2 rounded-lg border bg-card py-1 pr-1 pl-2.5"
    >
      <span className="font-mono text-xs font-semibold tracking-wider">{f.codigo}</span>
      {permissoes.escrever ? (
        <Select
          value={f.status}
          disabled={ocupado}
          onValueChange={(status) =>
            executar(() => mudarStatusFormulario(f.id, status), `${f.codigo}: ${status}`)
          }
        >
          <SelectTrigger className="h-7 w-28 text-[11px]" aria-label={`Status do DS-160 ${f.codigo}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {statusDs.map((st) => (
              <SelectItem key={st} value={st}>
                {st}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : (
        <span className="pr-1.5 text-[10px] text-muted-foreground uppercase">{f.status}</span>
      )}
      {permissoes.apagar && (
        <button
          type="button"
          disabled={ocupado}
          onClick={() => {
            if (confirm(`Remover o formulário ${f.codigo}?`))
              executar(() => removerFormulario(f.id), `${f.codigo} removido`);
          }}
          className="rounded p-1 text-muted-foreground hover:bg-perigo-suave hover:text-perigo"
          aria-label={`Remover o DS-160 ${f.codigo}`}
        >
          <Trash2 className="size-3.5" />
        </button>
      )}
    </li>
  );
}

function NovoCodigo({ solicitanteId, statusDs }: { solicitanteId: number; statusDs: string[] }) {
  const { ocupado, executar } = useAcao();
  const [codigo, setCodigo] = useState("");
  const [status, setStatus] = useState(statusDs[0] ?? "Pendente");
  const normalizado = normalizarCodigo(codigo);
  const invalido = codigo.trim() !== "" && !PADRAO_DS160.test(normalizado);

  return (
    <form
      className="mt-2 flex flex-wrap items-start gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (!PADRAO_DS160.test(normalizado)) return;
        executar(() => adicionarFormulario(solicitanteId, normalizado, status), `${normalizado} cadastrado`);
        setCodigo("");
      }}
    >
      <div>
        <Input
          value={codigo}
          onChange={(e) => setCodigo(e.target.value.toUpperCase())}
          placeholder="AA00XXXXXX"
          maxLength={12}
          aria-label="Código do DS-160"
          aria-invalid={invalido}
          className="h-8 w-36 font-mono text-xs tracking-wider"
        />
        {invalido && <p className="mt-1 text-[11px] text-perigo">AA00 + 6 letras ou números</p>}
      </div>
      <Select value={status} onValueChange={setStatus}>
        <SelectTrigger className="h-8 w-32 text-xs" aria-label="Status do novo DS-160">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {statusDs.map((st) => (
            <SelectItem key={st} value={st}>
              {st}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button
        type="submit"
        size="sm"
        variant="ghost"
        disabled={ocupado || !PADRAO_DS160.test(normalizado)}
        className="h-8"
      >
        <Plus className="size-4" /> DS-160
      </Button>
    </form>
  );
}
