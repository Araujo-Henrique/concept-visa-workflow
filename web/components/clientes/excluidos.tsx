"use client";

import { ArchiveRestore, ShieldAlert, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { eliminarCliente, restaurarCliente } from "@/app/acoes/excluidos";
import { nomeConfere } from "@/components/clientes/controles";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ClienteExcluido } from "@/lib/auditoria";
import { formatarTelefone } from "@/lib/formularios";
import { dataEHora } from "@/lib/processos";

/** O motivo precisa ter ao menos isto (a API confere de novo). */
export const MOTIVO_MINIMO = 5;

/** "Excluído em 10/11/2026 às 09:49 por Ana" (sem usuário: de onde veio). */
export function quemEQuando(c: Pick<ClienteExcluido, "apagado_em" | "apagado_por" | "origem">): string {
  const [dia, hora] = dataEHora(c.apagado_em);
  const quem = c.apagado_por ?? (c.origem === "banco" ? "alteração direta no banco" : c.origem);
  return `Excluído em ${dia} às ${hora} por ${quem}`;
}

export function ListaExcluidos({ clientes }: { clientes: ClienteExcluido[] }) {
  if (clientes.length === 0) {
    return (
      <div className="grid place-items-center rounded-2xl border border-dashed bg-card px-6 py-14 text-center">
        <ArchiveRestore className="size-8 text-marca" aria-hidden />
        <p className="mt-3 font-heading font-bold">Nenhum cliente excluído</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Quando alguém excluir um cliente, ele aparece aqui.
        </p>
      </div>
    );
  }
  return (
    <ul className="space-y-3">
      {clientes.map((c) => (
        <li key={c.cliente_id} className="rounded-2xl border bg-card p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="font-heading text-lg font-bold">{c.nome}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {[c.telefone && formatarTelefone(c.telefone), c.email].filter(Boolean).join(" · ") ||
                  "Sem telefone nem e-mail"}
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                {quemEQuando(c)} ·{" "}
                {c.n_processos === 0
                  ? "sem processos"
                  : c.n_processos === 1
                    ? "1 processo"
                    : `${c.n_processos} processos`}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Restaurar cliente={c} />
              <Eliminar cliente={c} />
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function Restaurar({ cliente }: { cliente: ClienteExcluido }) {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const [restaurando, iniciar] = useTransition();
  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        disabled={restaurando}
        onClick={() => {
          setErro(null);
          iniciar(async () => {
            const r = await restaurarCliente(cliente.cliente_id);
            if (r.ok) {
              const { processos, pessoas } = r.dados;
              toast.success("Cliente restaurado", {
                description: `${r.dados.nome}: ${processos} processo(s), ${pessoas} pessoa(s).`,
                action: {
                  label: "Abrir",
                  onClick: () => router.push(`/clientes/${cliente.cliente_id}`),
                },
              });
            } else setErro(r.erro);
          });
        }}
      >
        <ArchiveRestore className="size-4" /> {restaurando ? "Restaurando…" : "Restaurar"}
      </Button>
      {erro && (
        <p role="alert" className="max-w-xs rounded-lg bg-perigo/10 px-3 py-2 text-sm text-perigo">
          {erro}
        </p>
      )}
    </div>
  );
}

function Eliminar({ cliente }: { cliente: ClienteExcluido }) {
  const [aberto, setAberto] = useState(false);
  const [nome, setNome] = useState("");
  const [motivo, setMotivo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [eliminando, iniciar] = useTransition();
  const pronto = nomeConfere(nome, cliente.nome) && motivo.trim().length >= MOTIVO_MINIMO;

  const mudarAberto = (a: boolean) => {
    setAberto(a);
    if (!a) {
      setNome("");
      setMotivo("");
      setErro(null);
    }
  };

  return (
    <>
      <Button
        variant="outline"
        className="text-perigo hover:bg-perigo/10 hover:text-perigo"
        onClick={() => setAberto(true)}
      >
        <Trash2 className="size-4" /> Eliminar de vez
      </Button>
      <Dialog open={aberto} onOpenChange={mudarAberto}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldAlert className="size-5 text-perigo" aria-hidden /> Eliminar definitivamente?
            </DialogTitle>
            <DialogDescription>
              Apaga {cliente.nome} <strong>também da cópia de segurança</strong> (processos, pessoas, DS-160 e
              todo o histórico). <strong>Não existe volta.</strong> Use só quando o próprio cliente pedir ou o
              cadastro não tiver valor nenhum. Fica registrado apenas o número, quem eliminou, quando e o
              motivo.
            </DialogDescription>
          </DialogHeader>
          <form
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (!pronto) return;
              iniciar(async () => {
                const r = await eliminarCliente(cliente.cliente_id, nome, motivo);
                if (r.ok) {
                  toast.success("Cliente eliminado definitivamente");
                  mudarAberto(false);
                } else setErro(r.erro);
              });
            }}
          >
            <div className="grid gap-2">
              <Label htmlFor={`elim-nome-${cliente.cliente_id}`}>
                Para confirmar, digite o nome: <strong className="font-semibold">{cliente.nome}</strong>
              </Label>
              <Input
                id={`elim-nome-${cliente.cliente_id}`}
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                autoComplete="off"
                autoFocus
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor={`elim-motivo-${cliente.cliente_id}`}>
                Motivo <span className="font-normal text-muted-foreground">(não escreva dados pessoais)</span>
              </Label>
              <Textarea
                id={`elim-motivo-${cliente.cliente_id}`}
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
                maxLength={300}
                placeholder="Ex.: pedido do titular por e-mail em 10/11"
              />
            </div>
            {erro && (
              <p role="alert" className="rounded-lg bg-perigo/10 px-3 py-2 text-sm text-perigo">
                {erro}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => mudarAberto(false)}>
                Cancelar
              </Button>
              <Button type="submit" variant="destructive" disabled={!pronto || eliminando}>
                {eliminando ? "Eliminando…" : "Eliminar definitivamente"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** As eliminações já feitas (a "lápide": número, quem, quando e motivo; nenhum dado do cliente). */
export function Lapides({
  itens,
}: {
  itens: {
    id: number;
    registro_id: number;
    usuario_nome: string | null;
    criado_em: string;
    motivo: string;
  }[];
}) {
  if (itens.length === 0) return null;
  return (
    <section aria-label="Eliminações definitivas" className="mt-10">
      <h2 className="mb-3 font-heading text-sm font-bold tracking-wider uppercase">
        Eliminados definitivamente
      </h2>
      <ul className="space-y-2 text-sm">
        {itens.map((l) => {
          const [dia, hora] = dataEHora(l.criado_em);
          return (
            <li key={l.id} className="rounded-xl border bg-card px-4 py-3">
              <span className="font-medium">Cliente nº {l.registro_id}</span>
              <span className="text-muted-foreground">
                {" "}
                · {dia} às {hora} · por {l.usuario_nome ?? "—"} · {l.motivo}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function VoltarAosClientes() {
  return (
    <Link href="/clientes" className="text-sm text-muted-foreground hover:text-foreground">
      ← Clientes
    </Link>
  );
}
