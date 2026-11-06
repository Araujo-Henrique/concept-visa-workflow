"use client";

import { Search, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { buscar, type ItemBusca } from "@/app/acoes/processos";
import { SeloSituacao } from "@/components/processos/selos";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { cn } from "@/lib/utils";

/** Ctrl+K (ou ⌘K) em qualquer tela: número do processo (#1234) ou nome do cliente. */
export function BuscaGlobal({ className, atalho = true }: { className?: string; atalho?: boolean }) {
  const router = useRouter();
  const [aberta, setAberta] = useState(false);
  const [termo, setTermo] = useState("");
  const [itens, setItens] = useState<ItemBusca[]>([]);
  const [buscando, iniciar] = useTransition();

  useEffect(() => {
    if (!atalho) return;
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        setAberta((a) => !a);
      }
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [atalho]);

  useEffect(() => {
    const espera = setTimeout(
      () => iniciar(async () => setItens(termo.trim() ? await buscar(termo) : [])),
      250,
    );
    return () => clearTimeout(espera);
  }, [termo]);

  const abrir = (id: number) => {
    setAberta(false);
    setTermo("");
    router.push(`/processos/${id}`);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setAberta(true)}
        className={cn(
          "flex w-full items-center gap-2 rounded-xl border border-sidebar-border bg-sidebar-accent/50 px-3 py-2 text-sm text-sidebar-foreground/60 transition-colors hover:text-sidebar-foreground",
          className,
        )}
      >
        <Search className="size-4" />
        <span className="flex-1 text-left">Buscar…</span>
        <kbd className="rounded border border-sidebar-border px-1.5 font-mono text-[10px]">Ctrl K</kbd>
      </button>

      <CommandDialog
        open={aberta}
        onOpenChange={setAberta}
        title="Buscar processo"
        description="Digite o número do processo ou o nome do cliente"
      >
        {/* a API já filtra: o Command só mostra o que veio */}
        <Command shouldFilter={false}>
          <CommandInput
            value={termo}
            onValueChange={setTermo}
            placeholder="Nº do processo ou nome do cliente…"
          />
          <CommandList>
            {termo.trim() && !buscando && <CommandEmpty>Nenhum processo encontrado.</CommandEmpty>}
            {!termo.trim() && (
              <p className="px-4 py-6 text-center text-sm text-muted-foreground">
                Ex.: <span className="font-mono">#1234</span> ou <span className="font-medium">Souza</span>
              </p>
            )}
            {itens.length > 0 && (
              <CommandGroup heading="Processos">
                {itens.map((p) => (
                  <CommandItem
                    key={p.processo_id}
                    value={String(p.processo_id)}
                    onSelect={() => abrir(p.processo_id)}
                  >
                    <span className="w-14 font-heading text-xs font-bold tracking-wider text-muted-foreground">
                      #{p.processo_id}
                    </span>
                    <span className="font-heading text-[10px] font-bold tracking-widest text-marca-forte">
                      {p.tipo}
                    </span>
                    <span className="min-w-0 flex-1 truncate">{p.cliente}</span>
                    {p.n_solicitantes > 1 && (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Users className="size-3" /> {p.n_solicitantes}
                      </span>
                    )}
                    <SeloSituacao situacao={p.situacao} />
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </CommandDialog>
    </>
  );
}
