import "server-only";

import { cache } from "react";

import { apiGet } from "@/lib/api";
import type { Usuario } from "@/lib/tipos";

/**
 * Quem está logado. A API lê perfil e "ativo" do banco a cada requisição, então desativar alguém vale
 * na hora. `cache` evita repetir a chamada dentro da mesma renderização.
 */
export const usuarioAtual = cache(() => apiGet<Usuario>("/auth/eu"));
