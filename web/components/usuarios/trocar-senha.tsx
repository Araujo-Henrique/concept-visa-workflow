"use client";

import { LockKeyhole } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { trocarMinhaSenha } from "@/app/acoes/usuarios";
import { CampoSenha } from "@/components/usuarios/campo-senha";
import { Button } from "@/components/ui/button";
import { validarSenha, type Erros } from "@/lib/usuarios";

/** Trocar a própria senha: pede a atual (quem pegou o computador aberto não troca sozinho). */
export function TrocarSenha() {
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erros, setErros] = useState<Erros>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [salvando, iniciar] = useTransition();

  const salvar = () => {
    const encontrados: Erros = { ...validarSenha(nova, confirmacao) };
    if (!atual) encontrados.atual = "Informe a senha atual.";
    else if (nova && nova === atual) encontrados.senha = "A senha nova precisa ser diferente da atual.";
    setErros(encontrados);
    setErroGeral(null);
    if (Object.keys(encontrados).length) return;
    iniciar(async () => {
      const r = await trocarMinhaSenha(atual, nova);
      if (r.ok) {
        toast.success("Senha trocada", { description: "Use a senha nova no próximo login." });
        setAtual("");
        setNova("");
        setConfirmacao("");
      } else setErroGeral(r.erro);
    });
  };

  return (
    <form
      className="space-y-4"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        salvar();
      }}
    >
      <CampoSenha
        rotulo="Senha atual"
        valor={atual}
        aoMudar={setAtual}
        erro={erros.atual}
        autoComplete="current-password"
        dica=""
      />
      <CampoSenha rotulo="Senha nova" valor={nova} aoMudar={setNova} erro={erros.senha} />
      <CampoSenha
        rotulo="Repita a senha nova"
        valor={confirmacao}
        aoMudar={setConfirmacao}
        erro={erros.confirmacao}
        dica=""
      />
      {erroGeral && (
        <p role="alert" className="rounded-lg bg-perigo-suave px-3 py-2 text-sm text-perigo">
          {erroGeral}
        </p>
      )}
      <Button type="submit" disabled={salvando} className="h-10">
        <LockKeyhole className="size-4" /> {salvando ? "Trocando…" : "Trocar senha"}
      </Button>
    </form>
  );
}
