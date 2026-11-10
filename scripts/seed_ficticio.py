"""Popula o banco com dados FICTÍCIOS, só para a máquina de testes e demonstrações.

    python -m scripts.seed_ficticio --confirmo-dados-ficticios

NUNCA rode na máquina com dados reais: o comando exige a confirmação acima e recusa um banco que já tenha
clientes. Usa o DATABASE_URL do .env. A senha dos usuários demo (admin@, atendente@, leitor@ exemplo.com) é
pedida no terminal (não aparece na tela nem fica no histórico); com `--sem-senha`, ninguém entra por senha.
"""
import argparse
import getpass
import sys

from dotenv import load_dotenv
from sqlalchemy import make_url

from app import db
from app.seed import semear
from app.servicos.workflow import ErroDeRegra


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--confirmo-dados-ficticios", action="store_true",
                    help="obrigatório: confirma que este banco é de testes e que os dados criados são inventados")
    ap.add_argument("--sem-senha", action="store_true", help="cria os usuários demo sem senha")
    ap.add_argument("--clientes", type=int, default=36, help="quantidade de clientes (padrão: 36)")
    args = ap.parse_args()
    if not args.confirmo_dados_ficticios:
        print("Recusado: este comando cria dados inventados. Rode de novo com --confirmo-dados-ficticios "
              "se este for o banco de testes.")
        return 2

    load_dotenv()
    engine = db.configurar()
    print(f"Destino: {make_url(str(engine.url)).database}")

    senha = None
    if not args.sem_senha:
        senha = getpass.getpass("Senha dos usuários demo: ")
        if senha != getpass.getpass("Repita a senha: "):
            print("As senhas não conferem.")
            return 1
    try:
        with db.Session() as sessao:
            resumo = semear(sessao, senha, quantidade=args.clientes)
            sessao.commit()
    except (RuntimeError, ErroDeRegra) as erro:
        print(f"Recusado: {getattr(erro, 'mensagem', erro)}")
        return 1

    for chave, valor in resumo.items():
        print(f"  {chave:20}{valor:>6}")
    print("Pronto. Entre com a senha em admin@exemplo.com (os demais usuários demo entram só com o Google).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
