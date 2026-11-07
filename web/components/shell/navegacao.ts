import { CalendarDays, Home, ShieldCheck, Stamp, Users, type LucideIcon } from "lucide-react";

import type { Acao } from "@/lib/permissoes";

export type ItemMenu = {
  href: string;
  rotulo: string;
  icone: LucideIcon;
  /** permissão exigida para aparecer no menu (a API continua decidindo de verdade) */
  exige?: Acao;
  /** telas das próximas fases aparecem como "em breve" */
  pronto: boolean;
};

export const MENU: ItemMenu[] = [
  { href: "/", rotulo: "Início", icone: Home, pronto: true },
  { href: "/processos", rotulo: "Processos", icone: Stamp, pronto: true },
  { href: "/clientes", rotulo: "Clientes", icone: Users, pronto: true },
  { href: "/agenda", rotulo: "Agenda", icone: CalendarDays, pronto: false },
  { href: "/usuarios", rotulo: "Usuários", icone: ShieldCheck, exige: "administrar", pronto: false },
];

/** Item ativo: "/" só na raiz; os demais também nas subpáginas (/processos/12). */
export function ativo(href: string, caminho: string): boolean {
  return href === "/" ? caminho === "/" : caminho === href || caminho.startsWith(`${href}/`);
}
