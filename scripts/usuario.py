"""Criar usuário e definir senha pelo terminal. A senha é pedida com getpass: não aparece na tela, não vai
para o histórico do terminal e nunca entra no código nem no Git.

    python -m scripts.usuario criar --nome "Fulano de Tal" --email fulano@empresa.com.br --perfil admin
    python -m scripts.usuario senha --email fulano@empresa.com.br

`criar --sem-senha` cria o usuário só para o login com Google (etapa 5b). Para o primeiro administrador,
use `criar` com o perfil admin. Usa o DATABASE_URL do .env.
"""
import argparse
import getpass
import sys

from dotenv import load_dotenv

from app import db
from app.servicos.usuarios import criar_usuario, definir_senha
from app.servicos.workflow import ErroDeRegra


def pedir_senha() -> str:
    senha = getpass.getpass("Senha: ")
    if senha != getpass.getpass("Repita a senha: "):
        raise ErroDeRegra("As senhas não conferem")
    return senha


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)
    c = sub.add_parser("criar", help="cria um usuário")
    c.add_argument("--nome", required=True)
    c.add_argument("--email", required=True)
    c.add_argument("--perfil", required=True, help="admin, atendente ou leitor")
    c.add_argument("--sem-senha", action="store_true", help="só login com Google")
    s = sub.add_parser("senha", help="define ou troca a senha de um usuário existente")
    s.add_argument("--email", required=True)
    args = ap.parse_args()

    load_dotenv()
    db.configurar()
    try:
        with db.Session() as sessao:
            if args.comando == "criar":
                senha = None if args.sem_senha else pedir_senha()
                usuario = criar_usuario(sessao, args.nome, args.email, args.perfil, senha)
                print(f"Usuário criado: {usuario.nome} <{usuario.email}> ({args.perfil})")
            else:
                usuario = definir_senha(sessao, args.email, pedir_senha())
                print(f"Senha definida para {usuario.email}")
            sessao.commit()
    except ErroDeRegra as erro:
        print(f"Erro: {erro.mensagem}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
