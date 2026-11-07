"use client";

import { ChevronsUpDown, LogOut, Monitor, Moon, Pause, Sparkles, Sun, UserRound } from "lucide-react";
import Link from "next/link";
import { useTheme } from "next-themes";

import { sair } from "@/app/acoes/auth";
import { useMovimento } from "@/components/provedores";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { lerValor } from "@/lib/movimento";
import { NOME_DO_PERFIL } from "@/lib/permissoes";
import type { Usuario } from "@/lib/tipos";

export function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/);
  return ((partes[0]?.[0] ?? "") + (partes.length > 1 ? partes[partes.length - 1][0] : "")).toUpperCase();
}

export function MenuUsuario({ usuario }: { usuario: Usuario }) {
  const { theme, setTheme } = useTheme();
  const { preferencia, sistemaReduz, definir } = useMovimento();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full items-center gap-3 rounded-xl p-2 text-left outline-none transition-colors hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-sidebar-ring">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-marca font-heading text-sm font-bold text-tinta">
          {iniciais(usuario.nome)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold">{usuario.nome}</span>
          <span className="block truncate text-xs text-sidebar-foreground/60">
            {NOME_DO_PERFIL[usuario.perfil]}
          </span>
        </span>
        <ChevronsUpDown className="size-4 text-sidebar-foreground/50" />
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start" className="w-64">
        <DropdownMenuLabel className="font-normal">
          <span className="block text-sm font-semibold">{usuario.nome}</span>
          <span className="block truncate text-xs text-muted-foreground">{usuario.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuItem asChild>
          <Link href="/conta">
            <UserRound /> Minha conta
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="text-xs text-muted-foreground">Tema</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={theme} onValueChange={setTheme}>
          <DropdownMenuRadioItem value="light">
            <Sun /> Claro
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="dark">
            <Moon /> Escuro
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="system">
            <Monitor /> Igual ao sistema
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="text-xs text-muted-foreground">Animações</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={preferencia} onValueChange={(valor) => definir(lerValor(valor))}>
          <DropdownMenuRadioItem value="sistema" onSelect={(e) => e.preventDefault()}>
            <Monitor /> Seguir o sistema
            {sistemaReduz && <span className="ml-auto text-[10px] text-muted-foreground">(reduzidas)</span>}
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="ligado" onSelect={(e) => e.preventDefault()}>
            <Sparkles /> Sempre ligadas
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="reduzido" onSelect={(e) => e.preventDefault()}>
            <Pause /> Reduzidas
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <form action={sair} className="w-full">
            <button type="submit" className="flex w-full items-center gap-2">
              <LogOut className="size-4" /> Sair
            </button>
          </form>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
