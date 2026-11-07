"use client";

import { History, ShieldAlert } from "lucide-react";
import { useEffect, useState, useTransition } from "react";
import { toast } from "sonner";

import { auditoriaDoUsuario, criarUsuario, editarUsuario, redefinirSenha } from "@/app/acoes/usuarios";
import { CampoTexto } from "@/components/formularios/campos";
import { CampoSenha } from "@/components/usuarios/campo-senha";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { NOME_DO_PERFIL } from "@/lib/permissoes";
import { dataEHora } from "@/lib/processos";
import type { Perfil, Usuario } from "@/lib/tipos";
import {
  descreverAuditoria,
  DESCRICAO_DO_PERFIL,
  PERFIS,
  validarSenha,
  validarUsuarioNovo,
  type Erros,
  type RegistroAuditoria,
} from "@/lib/usuarios";
import { cn } from "@/lib/utils";

function ErroGeral({ erro }: { erro: string | null }) {
  if (!erro) return null;
  return (
    <p role="alert" className="rounded-lg bg-perigo-suave px-3 py-2 text-sm text-perigo">
      {erro}
    </p>
  );
}

function Rodape({
  salvando,
  rotulo,
  aoCancelar,
}: {
  salvando: boolean;
  rotulo: string;
  aoCancelar: () => void;
}) {
  return (
    <div className="flex justify-end gap-2 pt-2">
      <Button type="button" variant="ghost" onClick={aoCancelar}>
        Cancelar
      </Button>
      <Button type="submit" disabled={salvando}>
        {salvando ? "Salvando…" : rotulo}
      </Button>
    </div>
  );
}

/** Perfil como três cartões (com o que cada um pode), em vez de uma lista seca. */
function EscolhaDePerfil({ valor, aoMudar }: { valor: Perfil; aoMudar: (p: Perfil) => void }) {
  return (
    <fieldset className="space-y-1.5">
      <legend className="mb-1.5 text-sm font-medium">Perfil</legend>
      <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Perfil">
        {PERFIS.map((p) => (
          <button
            key={p}
            type="button"
            role="radio"
            aria-checked={valor === p}
            onClick={() => aoMudar(p)}
            className={cn(
              "rounded-xl border p-3 text-left transition-colors",
              valor === p ? "border-marca bg-marca-suave ring-1 ring-marca" : "hover:bg-muted",
            )}
          >
            <span className="block text-sm font-semibold">{NOME_DO_PERFIL[p]}</span>
            <span className="mt-0.5 block text-xs text-muted-foreground">{DESCRICAO_DO_PERFIL[p]}</span>
          </button>
        ))}
      </div>
    </fieldset>
  );
}

// ---------------------------------------------------------------- novo / editar

export function DialogoUsuario({
  aberto,
  aoMudarAberto,
  usuario,
}: {
  aberto: boolean;
  aoMudarAberto: (aberto: boolean) => void;
  /** sem usuário: cadastro novo */
  usuario?: Usuario | null;
}) {
  return (
    <Dialog open={aberto} onOpenChange={aoMudarAberto}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{usuario ? `Editar ${usuario.nome}` : "Novo usuário"}</DialogTitle>
          <DialogDescription>
            {usuario
              ? "O e-mail não muda: ele é a identidade de quem entra."
              : "Gere uma senha e mande para a pessoa. Ela pode trocar depois em Minha conta."}
          </DialogDescription>
        </DialogHeader>
        {aberto && (
          <FormUsuario key={usuario?.id ?? "novo"} usuario={usuario} aoFechar={() => aoMudarAberto(false)} />
        )}
      </DialogContent>
    </Dialog>
  );
}

function FormUsuario({ usuario, aoFechar }: { usuario?: Usuario | null; aoFechar: () => void }) {
  const [nome, setNome] = useState(usuario?.nome ?? "");
  const [email, setEmail] = useState(usuario?.email ?? "");
  const [perfil, setPerfil] = useState<Perfil>(usuario?.perfil ?? "atendente");
  const [senha, setSenha] = useState("");
  const [erros, setErros] = useState<Erros>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [salvando, iniciar] = useTransition();

  const salvar = () => {
    if (usuario) {
      const mudancas: { nome?: string; perfil?: Perfil } = {};
      if (nome.trim() !== usuario.nome) mudancas.nome = nome.trim();
      if (perfil !== usuario.perfil) mudancas.perfil = perfil;
      if (!nome.trim()) return setErros({ nome: "Informe o nome." });
      if (Object.keys(mudancas).length === 0) return aoFechar();
      return iniciar(async () => {
        const r = await editarUsuario(usuario.id, mudancas);
        if (r.ok) {
          toast.success("Usuário atualizado", { description: r.dados.nome });
          aoFechar();
        } else setErroGeral(r.erro);
      });
    }
    const encontrados = validarUsuarioNovo({ nome, email, senha });
    setErros(encontrados);
    if (Object.keys(encontrados).length) return;
    iniciar(async () => {
      const r = await criarUsuario({ nome: nome.trim(), email: email.trim().toLowerCase(), perfil, senha });
      if (r.ok) {
        toast.success("Usuário criado", { description: `${r.dados.nome} já pode entrar.` });
        aoFechar();
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
      <CampoTexto rotulo="Nome" valor={nome} aoMudar={setNome} erro={erros.nome} autoFocus />
      {!usuario && (
        <CampoTexto rotulo="E-mail" tipo="email" valor={email} aoMudar={setEmail} erro={erros.email} />
      )}
      <EscolhaDePerfil valor={perfil} aoMudar={setPerfil} />
      {!usuario && (
        <CampoSenha rotulo="Senha inicial" valor={senha} aoMudar={setSenha} erro={erros.senha} comGerador />
      )}
      <ErroGeral erro={erroGeral} />
      <Rodape
        salvando={salvando}
        rotulo={usuario ? "Salvar alterações" : "Criar usuário"}
        aoCancelar={aoFechar}
      />
    </form>
  );
}

// ---------------------------------------------------------------- senha

export function DialogoSenha({ usuario, aoFechar }: { usuario: Usuario | null; aoFechar: () => void }) {
  return (
    <Dialog open={Boolean(usuario)} onOpenChange={(a) => !a && aoFechar()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Redefinir a senha</DialogTitle>
          <DialogDescription>
            {usuario?.nome} passa a entrar com a senha nova. Copie e mande para a pessoa: depois de salvar,
            ela não aparece mais.
          </DialogDescription>
        </DialogHeader>
        {usuario && <FormSenha key={usuario.id} usuario={usuario} aoFechar={aoFechar} />}
      </DialogContent>
    </Dialog>
  );
}

function FormSenha({ usuario, aoFechar }: { usuario: Usuario; aoFechar: () => void }) {
  const [senha, setSenha] = useState("");
  const [erros, setErros] = useState<Erros>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [salvando, iniciar] = useTransition();
  return (
    <form
      className="space-y-4"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        const encontrados = validarSenha(senha);
        setErros(encontrados);
        if (Object.keys(encontrados).length) return;
        iniciar(async () => {
          const r = await redefinirSenha(usuario.id, senha);
          if (r.ok) {
            toast.success("Senha redefinida", { description: usuario.nome });
            aoFechar();
          } else setErroGeral(r.erro);
        });
      }}
    >
      <CampoSenha rotulo="Senha nova" valor={senha} aoMudar={setSenha} erro={erros.senha} comGerador />
      <ErroGeral erro={erroGeral} />
      <Rodape salvando={salvando} rotulo="Redefinir senha" aoCancelar={aoFechar} />
    </form>
  );
}

// ---------------------------------------------------------------- acesso

export function DialogoAcesso({ usuario, aoFechar }: { usuario: Usuario | null; aoFechar: () => void }) {
  const [salvando, iniciar] = useTransition();
  const [erro, setErro] = useState<string | null>(null);
  const desativar = Boolean(usuario?.ativo);

  return (
    <Dialog
      open={Boolean(usuario)}
      onOpenChange={(a) => {
        if (!a) {
          setErro(null);
          aoFechar();
        }
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {desativar && <ShieldAlert className="size-5 text-perigo" />}
            {desativar ? "Desativar o acesso?" : "Reativar o acesso?"}
          </DialogTitle>
          <DialogDescription>
            {desativar
              ? `${usuario?.nome} deixa de entrar na hora, mesmo que esteja com a sessão aberta. O histórico e os processos continuam.`
              : `${usuario?.nome} volta a entrar com a mesma senha de antes.`}
          </DialogDescription>
        </DialogHeader>
        <ErroGeral erro={erro} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button
            variant={desativar ? "destructive" : "default"}
            disabled={salvando}
            onClick={() =>
              usuario &&
              iniciar(async () => {
                const r = await editarUsuario(usuario.id, { ativo: !usuario.ativo });
                if (r.ok) {
                  toast.success(desativar ? "Acesso desativado" : "Acesso reativado", {
                    description: usuario.nome,
                  });
                  aoFechar();
                } else setErro(r.erro);
              })
            }
          >
            {salvando ? "Salvando…" : desativar ? "Desativar" : "Reativar"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------- histórico

export function HistoricoUsuario({
  usuario,
  nomes,
  aoFechar,
}: {
  usuario: Usuario | null;
  /** id -> nome, para dizer quem fez cada mudança */
  nomes: Record<number, string>;
  aoFechar: () => void;
}) {
  const [registros, setRegistros] = useState<RegistroAuditoria[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!usuario) return;
    let vivo = true;
    auditoriaDoUsuario(usuario.id).then((r) => {
      if (!vivo) return;
      if (r.ok) setRegistros([...r.dados].reverse());
      else setErro(r.erro);
    });
    return () => {
      vivo = false;
      setRegistros(null);
      setErro(null);
    };
  }, [usuario]);

  return (
    <Sheet open={Boolean(usuario)} onOpenChange={(a) => !a && aoFechar()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <History className="size-5 text-marca" /> Histórico de {usuario?.nome}
          </SheetTitle>
          <SheetDescription>
            Cada mudança de perfil, acesso, nome e senha. A senha em si nunca aparece.
          </SheetDescription>
        </SheetHeader>
        <div className="px-4 pb-6">
          {erro && <ErroGeral erro={erro} />}
          {!erro && !registros && (
            <div className="space-y-3" aria-hidden>
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          )}
          {registros?.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Nenhuma mudança registrada (usuário anterior à auditoria).
            </p>
          )}
          {registros && registros.length > 0 && (
            <ol className="relative space-y-4 border-l border-dashed pl-5">
              {registros.map((r) => {
                const [dia, hora] = dataEHora(r.criado_em);
                return (
                  <li key={r.id} className="relative">
                    <span className="absolute top-1.5 -left-[25px] size-2.5 rounded-full bg-marca ring-4 ring-background" />
                    <p className="text-sm font-medium">{descreverAuditoria(r)}</p>
                    <p className="text-xs text-muted-foreground">
                      {dia} às {hora}
                      {r.feito_por_id !== null &&
                        ` · por ${nomes[r.feito_por_id] ?? `usuário #${r.feito_por_id}`}`}
                    </p>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
