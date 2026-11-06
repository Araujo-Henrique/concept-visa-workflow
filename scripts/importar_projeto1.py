"""Importa os dados do banco do Projeto 1 para o banco deste projeto.

Uso (na raiz do projeto, com a venv ativa):
    python -m scripts.importar_projeto1 --simular               # roda tudo e DESFAZ no final (ensaio)
    python -m scripts.importar_projeto1 --usuarios usuarios.csv # grava de verdade
    (nos dois modos, as exceções vão para excecoes_importacao.csv; mude com --excecoes caminho.csv)

Variáveis do .env (cada máquina tem as suas):
    SOURCE_DATABASE_URL   banco antigo (Projeto 1), só leitura
    DATABASE_URL          banco novo, já com `alembic upgrade head` e VAZIO

--usuarios é opcional: CSV local (fora do Git) com `nome;email;perfil` dos funcionários que viram usuários.
"""
import argparse
import os
import sys

import psycopg
from dotenv import load_dotenv
from sqlalchemy import make_url

from app import db
from app.importacao.projeto1 import carregar_usuarios_csv, importar


def _sem_driver(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--simular", action="store_true", help="faz tudo e desfaz no final, sem gravar nada")
    ap.add_argument("--usuarios", help="CSV nome;email;perfil dos funcionários que viram usuários")
    ap.add_argument("--excecoes", default="excecoes_importacao.csv",
                    help="CSV com tudo o que foi decidido por regra e merece olhar humano (fica fora do Git)")
    args = ap.parse_args()

    load_dotenv()
    origem_url, destino_url = os.environ.get("SOURCE_DATABASE_URL"), os.environ.get("DATABASE_URL")
    if not origem_url or not destino_url:
        print("Defina SOURCE_DATABASE_URL e DATABASE_URL no .env (veja .env.example)")
        return 2
    nome_origem, nome_destino = make_url(origem_url).database, make_url(destino_url).database
    if nome_origem == nome_destino:
        print("Origem e destino são o mesmo banco: recusado.")
        return 2
    print(f"Origem : {nome_origem} (somente leitura)")
    print(f"Destino: {nome_destino}")
    print("Modo   :", "SIMULAÇÃO (nada será gravado)" if args.simular else "GRAVAÇÃO")

    usuarios = carregar_usuarios_csv(args.usuarios) if args.usuarios else None
    db.configurar(destino_url)
    with psycopg.connect(_sem_driver(origem_url)) as origem, db.Session() as sessao:
        origem.read_only = True
        try:
            relatorio = importar(origem, sessao, usuarios)
        except Exception:
            sessao.rollback()
            raise
        if args.simular or not relatorio.confere():
            sessao.rollback()
        else:
            sessao.commit()

    print(f"\n{'':40}{'origem':>10}{'destino':>10}")
    for chave in relatorio.origem:
        marca = "" if relatorio.origem[chave] == relatorio.destino[chave] else "  <- diferente"
        print(f"{chave:40}{relatorio.origem[chave]:>10}{relatorio.destino[chave]:>10}{marca}")
    if relatorio.normalizados:
        print("\nCorreções automáticas (registros alterados):")
        for campo, n in sorted(relatorio.normalizados.items()):
            print(f"  {campo:45}{n:>8}")
    por_categoria = relatorio.por_categoria()
    if por_categoria:
        print("\nExceções por categoria (detalhe no CSV):")
        for categoria, n in por_categoria.most_common():
            print(f"  {categoria:45}{n:>8}")
    relatorio.exportar_csv(args.excecoes)
    print(f"\n{len(relatorio.excecoes)} exceções exportadas em {args.excecoes}")
    for aviso in relatorio.avisos:
        if "[" not in aviso:  # os demais avisos já estão no CSV
            print(" -", aviso)

    if not relatorio.confere():
        print("\nFALHA: a conferência não bateu. NADA foi gravado.")
        return 1
    print("\nSimulação concluída: nada foi gravado." if args.simular else "\nImportação gravada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
