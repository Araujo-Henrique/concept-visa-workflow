/**
 * @jest-environment jsdom
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { criarUsuario, trocarMinhaSenha } from "@/app/acoes/usuarios";
import { Tripulacao } from "@/components/usuarios/tripulacao";
import { TrocarSenha } from "@/components/usuarios/trocar-senha";
import type { Usuario } from "@/lib/tipos";

jest.mock("@/app/acoes/usuarios", () => ({
  criarUsuario: jest.fn(),
  editarUsuario: jest.fn(),
  redefinirSenha: jest.fn(),
  auditoriaDoUsuario: jest.fn(),
  trocarMinhaSenha: jest.fn(),
}));
jest.mock("sonner", () => ({ toast: { success: jest.fn() } }));

const criar = criarUsuario as jest.MockedFunction<typeof criarUsuario>;
const trocar = trocarMinhaSenha as jest.MockedFunction<typeof trocarMinhaSenha>;

const usuarios: Usuario[] = [
  { id: 1, nome: "Henrique Araujo", email: "henrique@exemplo.com", ativo: true, perfil: "admin" },
  { id: 2, nome: "Bruna Lima", email: "bruna@exemplo.com", ativo: true, perfil: "atendente" },
  { id: 3, nome: "Carlos Dias", email: "carlos@exemplo.com", ativo: false, perfil: "leitor" },
];

describe("Usuários", () => {
  beforeEach(() => jest.clearAllMocks());

  it("mostra quem tem acesso; o filtro 'Sem acesso' mostra os desativados", async () => {
    render(<Tripulacao usuarios={usuarios} euId={1} />);
    expect(screen.getByRole("article", { name: "Henrique Araujo" })).toHaveTextContent("você");
    expect(screen.queryByRole("article", { name: "Carlos Dias" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Sem acesso/ }));
    expect(screen.getByRole("article", { name: "Carlos Dias" })).toBeInTheDocument();
    expect(screen.queryByRole("article", { name: "Bruna Lima" })).not.toBeInTheDocument();
  });

  it("ninguém se desativa pelo próprio crachá", async () => {
    render(<Tripulacao usuarios={usuarios} euId={1} />);
    await userEvent.click(screen.getByRole("button", { name: "Ações para Henrique Araujo" }));
    expect(await screen.findByRole("menuitem", { name: /Você não pode se desativar/ })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("novo usuário: confere a senha antes e envia o e-mail em minúsculas com o perfil escolhido", async () => {
    criar.mockResolvedValue({ ok: true, dados: { ...usuarios[1]!, id: 9, nome: "Dora" } });
    render(<Tripulacao usuarios={usuarios} euId={1} />);
    await userEvent.click(screen.getByRole("button", { name: "Novo usuário" }));
    const dialogo = within(await screen.findByRole("dialog"));
    await userEvent.type(dialogo.getByLabelText("Nome"), "Dora");
    await userEvent.type(dialogo.getByLabelText("E-mail"), "Dora@Exemplo.com");
    await userEvent.click(dialogo.getByRole("radio", { name: /Leitor/ }));
    await userEvent.type(dialogo.getByLabelText("Senha inicial"), "curta");
    await userEvent.click(dialogo.getByRole("button", { name: "Criar usuário" }));
    expect(dialogo.getByText(/pelo menos 10 caracteres/)).toBeInTheDocument();
    expect(criar).not.toHaveBeenCalled();

    await userEvent.click(dialogo.getByRole("button", { name: /Gerar/ }));
    await userEvent.click(dialogo.getByRole("button", { name: "Criar usuário" }));
    expect(criar).toHaveBeenCalledWith(
      expect.objectContaining({ nome: "Dora", email: "dora@exemplo.com", perfil: "leitor" }),
    );
  });
});

describe("Minha conta: trocar senha", () => {
  beforeEach(() => jest.clearAllMocks());

  it("confirmação diferente não envia; erro da API aparece", async () => {
    trocar.mockResolvedValue({ ok: false, erro: "Senha atual incorreta" });
    render(<TrocarSenha />);
    await userEvent.type(screen.getByLabelText("Senha atual"), "antiga-123456");
    await userEvent.type(screen.getByLabelText("Senha nova"), "nova-senha-123");
    await userEvent.type(screen.getByLabelText("Repita a senha nova"), "outra-coisa-123");
    await userEvent.click(screen.getByRole("button", { name: /Trocar senha/ }));
    expect(screen.getByText("As senhas não conferem.")).toBeInTheDocument();
    expect(trocar).not.toHaveBeenCalled();

    await userEvent.clear(screen.getByLabelText("Repita a senha nova"));
    await userEvent.type(screen.getByLabelText("Repita a senha nova"), "nova-senha-123");
    await userEvent.click(screen.getByRole("button", { name: /Trocar senha/ }));
    expect(trocar).toHaveBeenCalledWith("antiga-123456", "nova-senha-123");
    expect(await screen.findByRole("alert")).toHaveTextContent("Senha atual incorreta");
  });
});
