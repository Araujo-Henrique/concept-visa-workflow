"use client";

import { ChevronLeft, ChevronRight, Pencil, Plus, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { toast } from "sonner";

import { DialogoCliente } from "@/components/clientes/form-cliente";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Cliente } from "@/lib/tipos";

/** Busca da lista de clientes (nome, e-mail ou telefone), guardada na URL. */
export function BuscaClientes({ inicial }: { inicial: string }) {
  const router = useRouter();
  const [termo, setTermo] = useState(inicial);
  const [, iniciar] = useTransition();

  useEffect(() => {
    if (termo === inicial) return;
    const espera = setTimeout(
      () =>
        iniciar(() =>
          router.replace(termo.trim() ? `/clientes?busca=${encodeURIComponent(termo.trim())}` : "/clientes"),
        ),
      350,
    );
    return () => clearTimeout(espera);
  }, [termo, inicial, router]);

  return (
    <label className="relative block max-w-md flex-1">
      <span className="sr-only">Buscar cliente</span>
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        value={termo}
        onChange={(e) => setTermo(e.target.value)}
        placeholder="Nome, e-mail ou telefone…"
        className="h-11 bg-card pl-9"
      />
    </label>
  );
}

export function NovoCliente() {
  const router = useRouter();
  const [aberto, setAberto] = useState(false);
  return (
    <>
      <Button onClick={() => setAberto(true)} className="h-11">
        <Plus className="size-4" /> Novo cliente
      </Button>
      <DialogoCliente
        aberto={aberto}
        aoMudarAberto={setAberto}
        aoSalvar={(c) => {
          toast.success("Cliente cadastrado", { description: c.nome });
          router.push(`/clientes/${c.id}`);
        }}
      />
    </>
  );
}

export function EditarCliente({ cliente }: { cliente: Cliente }) {
  const [aberto, setAberto] = useState(false);
  return (
    <>
      <Button variant="outline" onClick={() => setAberto(true)}>
        <Pencil className="size-4" /> Editar
      </Button>
      <DialogoCliente
        aberto={aberto}
        aoMudarAberto={setAberto}
        cliente={cliente}
        aoSalvar={() => toast.success("Cliente atualizado")}
      />
    </>
  );
}

export function PaginacaoClientes({
  pagina,
  total,
  porPagina,
  busca,
}: {
  pagina: number;
  total: number;
  porPagina: number;
  busca: string;
}) {
  const router = useRouter();
  const paginas = Math.max(1, Math.ceil(total / porPagina));
  if (total === 0) return null;
  const ir = (p: number) => {
    const q = new URLSearchParams();
    if (busca) q.set("busca", busca);
    if (p > 1) q.set("pagina", String(p));
    router.replace(`/clientes${q.size ? `?${q}` : ""}`);
  };
  return (
    <nav aria-label="Páginas" className="mt-4 flex items-center justify-between text-sm">
      <p className="text-muted-foreground">
        <strong className="text-foreground">{total.toLocaleString("pt-BR")}</strong> clientes
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={pagina <= 1}
          onClick={() => ir(pagina - 1)}
          className="flex h-9 items-center gap-1 rounded-lg border bg-card px-3 disabled:opacity-40"
        >
          <ChevronLeft className="size-4" /> Anterior
        </button>
        <span className="px-2 text-muted-foreground tabular-nums">
          {pagina} / {paginas}
        </span>
        <button
          type="button"
          disabled={pagina >= paginas}
          onClick={() => ir(pagina + 1)}
          className="flex h-9 items-center gap-1 rounded-lg border bg-card px-3 disabled:opacity-40"
        >
          Próxima <ChevronRight className="size-4" />
        </button>
      </div>
    </nav>
  );
}
