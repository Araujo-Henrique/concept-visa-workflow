"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Logotipo } from "@/components/marca/logotipo";
import { Simbolo } from "@/components/marca/simbolo";
import { BuscaGlobal } from "@/components/shell/busca-global";
import { GuardaSessao } from "@/components/shell/guarda-sessao";
import { MenuUsuario } from "@/components/shell/menu-usuario";
import { ativo, MENU } from "@/components/shell/navegacao";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { pode } from "@/lib/permissoes";
import type { Usuario } from "@/lib/tipos";
import { cn } from "@/lib/utils";

function Navegacao({ usuario, aoNavegar }: { usuario: Usuario; aoNavegar?: () => void }) {
  const caminho = usePathname();
  const itens = MENU.filter((item) => !item.exige || pode(usuario.perfil, item.exige));

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="px-6 pt-7 pb-8">
        <Link
          href="/"
          onClick={aoNavegar}
          className="inline-block rounded-md outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
        >
          <Logotipo claro className="text-[1.35rem]" />
        </Link>
      </div>

      <div className="px-3 pb-4">
        {/* só a instância da lateral escuta o Ctrl+K (a do menu do celular é só o botão) */}
        <BuscaGlobal atalho={!aoNavegar} />
      </div>

      <nav aria-label="Principal" className="flex-1 px-3">
        <ul className="space-y-1">
          {itens.map(({ href, rotulo, icone: Icone, pronto }) => {
            const atual = ativo(href, caminho);
            const classes = cn(
              "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
              atual
                ? "bg-sidebar-accent text-white"
                : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-white",
              !pronto &&
                "cursor-not-allowed opacity-45 hover:bg-transparent hover:text-sidebar-foreground/75",
            );
            const conteudo = (
              <>
                {atual && (
                  <span className="absolute inset-y-2 left-0 w-1 rounded-full bg-marca" aria-hidden />
                )}
                <Icone className={cn("size-[18px]", atual && "text-marca")} />
                {rotulo}
                {!pronto && (
                  <span className="ml-auto rounded-full border border-sidebar-foreground/20 px-2 py-0.5 text-[10px] uppercase tracking-wider">
                    em breve
                  </span>
                )}
              </>
            );
            return (
              <li key={href}>
                {pronto ? (
                  <Link
                    href={href}
                    onClick={aoNavegar}
                    aria-current={atual ? "page" : undefined}
                    className={classes}
                  >
                    {conteudo}
                  </Link>
                ) : (
                  <span aria-disabled className={classes}>
                    {conteudo}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-sidebar-border p-3">
        <MenuUsuario usuario={usuario} />
      </div>
    </div>
  );
}

export function Estrutura({ usuario, children }: { usuario: Usuario; children: ReactNode }) {
  const [aberto, setAberto] = useState(false);

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[260px_1fr]">
      <aside className="sticky top-0 hidden h-dvh lg:block">
        <Navegacao usuario={usuario} />
      </aside>

      <div className="flex min-w-0 flex-col">
        {/* barra do celular */}
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b bg-background/85 px-4 py-3 backdrop-blur lg:hidden">
          <Sheet open={aberto} onOpenChange={setAberto}>
            <SheetTrigger
              className="grid size-10 place-items-center rounded-lg hover:bg-muted"
              aria-label="Abrir menu"
            >
              <Menu className="size-5" />
            </SheetTrigger>
            <SheetContent side="left" className="w-[280px] border-0 p-0">
              <SheetTitle className="sr-only">Menu</SheetTitle>
              <Navegacao usuario={usuario} aoNavegar={() => setAberto(false)} />
            </SheetContent>
          </Sheet>
          <Simbolo className="h-7" />
          <span className="font-heading text-sm font-extrabold tracking-wider">CONCEPT VISTOS</span>
        </header>

        <main className="flex-1 px-4 py-6 sm:px-8 lg:px-10 lg:py-10">{children}</main>
        <GuardaSessao />
      </div>
    </div>
  );
}
