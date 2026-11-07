"use client";

import { useState, useTransition } from "react";

import { criarCliente, editarCliente } from "@/app/acoes/clientes";
import { CampoTexto } from "@/components/formularios/campos";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { corpoCliente, validarCliente, type Erros, type Valores } from "@/lib/formularios";
import type { Cliente } from "@/lib/tipos";

const vazio: Valores = { nome: "", email: "", telefone: "", grupo: "" };

function valoresDe(c?: Cliente | null): Valores {
  if (!c) return vazio;
  return { nome: c.nome, email: c.email ?? "", telefone: c.telefone ?? "", grupo: c.grupo ?? "" };
}

/** Campos do cliente + salvar (cria ou edita). Usado no diálogo e dentro do assistente de processo novo. */
export function FormCliente({
  cliente,
  nomeInicial,
  aoSalvar,
  aoCancelar,
}: {
  cliente?: Cliente | null;
  nomeInicial?: string;
  aoSalvar: (cliente: Cliente) => void;
  aoCancelar?: () => void;
}) {
  const [valores, setValores] = useState<Valores>(() => ({
    ...valoresDe(cliente),
    ...(nomeInicial && !cliente ? { nome: nomeInicial } : {}),
  }));
  const [erros, setErros] = useState<Erros>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [salvando, iniciar] = useTransition();
  const mudar = (campo: string) => (v: string) => setValores((atual) => ({ ...atual, [campo]: v }));

  function salvar() {
    const encontrados = validarCliente(valores);
    setErros(encontrados);
    if (Object.keys(encontrados).length) return;
    const corpo = corpoCliente(valores);
    iniciar(async () => {
      const r = cliente
        ? await editarCliente(
            cliente.id,
            Object.fromEntries(
              Object.entries(corpo).filter(([k, v]) => v !== (cliente[k as keyof Cliente] ?? null)),
            ),
          )
        : await criarCliente(corpo);
      if (r.ok) aoSalvar(r.dados);
      else setErroGeral(r.erro.includes("Já existe") ? "Já existe um cliente com esse nome." : r.erro);
    });
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation(); // pode estar dentro de outro formulário (assistente)
        salvar();
      }}
      className="space-y-4"
      noValidate
    >
      <CampoTexto
        rotulo="Nome"
        obrigatorio
        autoFocus
        valor={valores.nome}
        aoMudar={mudar("nome")}
        erro={erros.nome}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <CampoTexto
          rotulo="Telefone"
          tipo="tel"
          placeholder="(41) 99999-0000"
          valor={valores.telefone}
          aoMudar={mudar("telefone")}
          erro={erros.telefone}
        />
        <CampoTexto
          rotulo="E-mail"
          tipo="email"
          valor={valores.email}
          aoMudar={mudar("email")}
          erro={erros.email}
        />
      </div>
      <CampoTexto
        rotulo="Grupo"
        dica="Família ou agência que viaja junto (opcional)."
        valor={valores.grupo}
        aoMudar={mudar("grupo")}
      />
      {erroGeral && (
        <p role="alert" className="rounded-lg bg-perigo-suave px-3 py-2 text-sm text-perigo">
          {erroGeral}
        </p>
      )}
      <div className="flex justify-end gap-2">
        {aoCancelar && (
          <Button type="button" variant="ghost" onClick={aoCancelar}>
            Cancelar
          </Button>
        )}
        <Button type="submit" disabled={salvando}>
          {salvando ? "Salvando…" : cliente ? "Salvar alterações" : "Cadastrar cliente"}
        </Button>
      </div>
    </form>
  );
}

export function DialogoCliente({
  aberto,
  aoMudarAberto,
  cliente,
  aoSalvar,
}: {
  aberto: boolean;
  aoMudarAberto: (aberto: boolean) => void;
  cliente?: Cliente | null;
  aoSalvar: (cliente: Cliente) => void;
}) {
  return (
    <Dialog open={aberto} onOpenChange={aoMudarAberto}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{cliente ? "Editar cliente" : "Novo cliente"}</DialogTitle>
          <DialogDescription>
            {cliente
              ? "As mudanças valem para todos os processos dele."
              : "O nome não pode repetir outro cliente."}
          </DialogDescription>
        </DialogHeader>
        {aberto && (
          <FormCliente
            key={cliente?.id ?? "novo"}
            cliente={cliente}
            aoSalvar={(c) => {
              aoMudarAberto(false);
              aoSalvar(c);
            }}
            aoCancelar={() => aoMudarAberto(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
