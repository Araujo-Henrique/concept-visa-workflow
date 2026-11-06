import { NextResponse, type NextRequest } from "next/server";

import { COOKIE_SESSAO } from "@/lib/constantes";

/**
 * Checagem otimista: sem o cookie de sessão, vai para o login (guardando para onde a pessoa ia).
 * A checagem de verdade é da API, a cada chamada (lib/api.ts redireciona quando ela responde 401).
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has(COOKIE_SESSAO)) return NextResponse.next();
  const login = new URL("/login", request.url);
  const { pathname, search } = request.nextUrl;
  if (pathname !== "/") login.searchParams.set("de", pathname + search);
  return NextResponse.redirect(login);
}

export const config = {
  // tudo, menos o próprio login, os arquivos do Next e os estáticos
  matcher: [
    "/((?!login|api|_next/static|_next/image|icon.svg|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|webp|ico)$).*)",
  ],
};
