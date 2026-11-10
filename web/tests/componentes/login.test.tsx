/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { FormLogin } from "@/components/login/form-login";

jest.mock("@/app/acoes/auth", () => ({ entrar: jest.fn() }));
jest.mock("next/navigation", () => ({ useRouter: () => ({ replace: jest.fn() }) }));
jest.mock("motion/react", () => ({
  motion: new Proxy({}, { get: () => "div" }),
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe("Login: Google primeiro, senha só como reserva do administrador", () => {
  it("o botão do Google é o caminho principal e a senha fica recolhida", () => {
    render(<FormLogin destino="/" expirou={false} />);
    expect(screen.getByRole("link", { name: /Entrar com o Google/ })).toHaveAttribute(
      "href",
      "/api/auth/google",
    );
    expect(screen.queryByLabelText("Senha")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("E-mail")).not.toBeInTheDocument();
    expect(screen.getByText(/Quem não estiver cadastrado não entra/)).toBeInTheDocument();
  });

  it("guarda para onde a pessoa ia, para voltar depois do Google", () => {
    render(<FormLogin destino="/processos?tipo=REN" expirou={false} />);
    expect(screen.getByRole("link", { name: /Entrar com o Google/ })).toHaveAttribute(
      "href",
      "/api/auth/google?de=%2Fprocessos%3Ftipo%3DREN",
    );
  });

  it("o administrador abre o acesso por senha", async () => {
    render(<FormLogin destino="/" expirou={false} />);
    await userEvent.click(screen.getByRole("button", { name: /Sou administrador e entro com senha/ }));
    expect(screen.getByLabelText("E-mail")).toBeInTheDocument();
    expect(screen.getByLabelText("Senha")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Sou administrador/ })).not.toBeInTheDocument();
  });

  it("mostra por que o Google não deixou entrar", () => {
    render(<FormLogin destino="/" expirou={false} erroGoogle="Este e-mail não tem acesso ao sistema." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Este e-mail não tem acesso ao sistema.");
  });

  it("sessão expirada continua avisando", () => {
    render(<FormLogin destino="/" expirou />);
    expect(screen.getByText(/Sua sessão expirou/)).toBeInTheDocument();
  });
});
