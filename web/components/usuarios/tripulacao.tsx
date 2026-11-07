"use client";

import { History, KeyRound, MoreHorizontal, Pencil, Plus, Power, Search } from "lucide-react";
import { useMemo, useState } from "react";

import {
  DialogoAcesso,
  DialogoSenha,
  DialogoUsuario,
  HistoricoUsuario,
} from "@/components/usuarios/dialogos";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { NOME_DO_PERFIL } from "@/lib/permissoes";
import type { Perfil, Usuario } from "@/lib/tipos";
import { iniciais } from "@/lib/usuarios";
import { cn } from "@/lib/utils";

type Filtro = "ativos" | "inativos" | "todos";

const COR_DO_PERFIL: Record<Perfil, string> = {
  admin: "bg-tinta text-papel dark:bg-papel dark:text-tinta",
  atendente: "bg-marca-forte text-white dark:bg-marca dark:text-tinta",
  leitor: "bg-muted text-foreground",
};

/** A equipe como crachás de tripulação. Quem está sem acesso aparece apagado, com o carimbo. */
export function Tripulacao({ usuarios, euId }: { usuarios: Usuario[]; euId: number }) {
  const [filtro, setFiltro] = useState<Filtro>("ativos");
  const [busca, setBusca] = useState("");
  const [novo, setNovo] = useState(false);
  const [editando, setEditando] = useState<Usuario | null>(null);
  const [senhaDe, setSenhaDe] = useState<Usuario | null>(null);
  const [acessoDe, setAcessoDe] = useState<Usuario | null>(null);
  const [historicoDe, setHistoricoDe] = useState<Usuario | null>(null);

  const nomes = useMemo(() => Object.fromEntries(usuarios.map((u) => [u.id, u.nome])), [usuarios]);
  const contagem = {
    ativos: usuarios.filter((u) => u.ativo).length,
    inativos: usuarios.filter((u) => !u.ativo).length,
    todos: usuarios.length,
  };
  const termo = busca.trim().toLowerCase();
  const visiveis = usuarios
    .filter((u) => (filtro === "todos" ? true : filtro === "ativos" ? u.ativo : !u.ativo))
    .filter((u) => !termo || u.nome.toLowerCase().includes(termo) || u.email.includes(termo))
    .sort((a, b) => Number(b.ativo) - Number(a.ativo) || a.nome.localeCompare(b.nome, "pt-BR"));

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-xl bg-muted p-1" role="group" aria-label="Mostrar">
          {(
            [
              ["ativos", "Com acesso"],
              ["inativos", "Sem acesso"],
              ["todos", "Todos"],
            ] as const
          ).map(([valor, rotulo]) => (
            <button
              key={valor}
              type="button"
              aria-pressed={filtro === valor}
              onClick={() => setFiltro(valor)}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors",
                filtro === valor ? "bg-card shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {rotulo}
              <span className="rounded-full bg-background px-1.5 text-[11px] text-muted-foreground tabular-nums">
                {contagem[valor]}
              </span>
            </button>
          ))}
        </div>
        <div className="flex flex-1 flex-wrap items-center justify-end gap-3">
          <label className="relative w-full max-w-xs">
            <span className="sr-only">Buscar usuário</span>
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Nome ou e-mail…"
              className="h-11 bg-card pl-9"
            />
          </label>
          <Button className="h-11" onClick={() => setNovo(true)}>
            <Plus className="size-4" /> Novo usuário
          </Button>
        </div>
      </div>

      {visiveis.length === 0 ? (
        <p className="rounded-2xl border border-dashed p-10 text-center text-muted-foreground">
          Ninguém por aqui com esse filtro.
        </p>
      ) : (
        <ul className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {visiveis.map((u) => (
            <li key={u.id}>
              <Cracha
                usuario={u}
                eu={u.id === euId}
                aoEditar={() => setEditando(u)}
                aoSenha={() => setSenhaDe(u)}
                aoAcesso={() => setAcessoDe(u)}
                aoHistorico={() => setHistoricoDe(u)}
              />
            </li>
          ))}
        </ul>
      )}

      <DialogoUsuario aberto={novo} aoMudarAberto={setNovo} />
      <DialogoUsuario
        aberto={Boolean(editando)}
        aoMudarAberto={(a) => !a && setEditando(null)}
        usuario={editando}
      />
      <DialogoSenha usuario={senhaDe} aoFechar={() => setSenhaDe(null)} />
      <DialogoAcesso usuario={acessoDe} aoFechar={() => setAcessoDe(null)} />
      <HistoricoUsuario usuario={historicoDe} nomes={nomes} aoFechar={() => setHistoricoDe(null)} />
    </>
  );
}

function Cracha({
  usuario,
  eu,
  aoEditar,
  aoSenha,
  aoAcesso,
  aoHistorico,
}: {
  usuario: Usuario;
  eu: boolean;
  aoEditar: () => void;
  aoSenha: () => void;
  aoAcesso: () => void;
  aoHistorico: () => void;
}) {
  return (
    <article
      aria-label={usuario.nome}
      className={cn(
        "relative overflow-hidden rounded-2xl border bg-card shadow-sm transition-shadow hover:shadow-md",
        !usuario.ativo && "opacity-70 grayscale",
      )}
    >
      {/* faixa do crachá, com o furo do cordão */}
      <div className="relative flex h-12 items-center justify-between bg-tinta px-4 text-papel dark:bg-muted">
        <span className="font-heading text-[10px] font-bold tracking-[0.3em]">TRIPULAÇÃO</span>
        <span
          className="absolute top-3 left-1/2 h-2 w-10 -translate-x-1/2 rounded-full bg-background"
          aria-hidden
        />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              className="text-papel hover:bg-white/10 hover:text-papel aria-expanded:bg-white/10 aria-expanded:text-papel"
              aria-label={`Ações para ${usuario.nome}`}
            >
              <MoreHorizontal className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            <DropdownMenuItem onSelect={aoEditar}>
              <Pencil /> Editar nome e perfil
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={aoSenha}>
              <KeyRound /> Redefinir senha
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={aoHistorico}>
              <History /> Ver histórico
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={aoAcesso}
              variant={usuario.ativo ? "destructive" : "default"}
              disabled={eu && usuario.ativo}
            >
              <Power />{" "}
              {usuario.ativo ? (eu ? "Você não pode se desativar" : "Desativar acesso") : "Reativar acesso"}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="flex items-center gap-4 p-5">
        <span
          className={cn(
            "grid size-14 shrink-0 place-items-center rounded-full font-heading text-lg font-extrabold",
            COR_DO_PERFIL[usuario.perfil],
          )}
          aria-hidden
        >
          {iniciais(usuario.nome)}
        </span>
        <div className="min-w-0">
          <p className="flex items-center gap-2 truncate font-semibold">
            <span className="truncate">{usuario.nome}</span>
            {eu && (
              <span className="shrink-0 rounded-full bg-marca-suave px-2 py-0.5 text-[10px] font-bold text-accent-foreground uppercase">
                você
              </span>
            )}
          </p>
          <p className="truncate text-sm text-muted-foreground">{usuario.email}</p>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-heading text-[11px] font-bold tracking-[0.2em] text-marca-forte uppercase">
              {NOME_DO_PERFIL[usuario.perfil]}
            </span>
            {!usuario.ativo && (
              <span className="-rotate-6 rounded-md border-2 border-perigo px-1.5 font-heading text-[10px] font-extrabold tracking-widest text-perigo uppercase">
                Sem acesso
              </span>
            )}
          </p>
        </div>
      </div>
    </article>
  );
}
