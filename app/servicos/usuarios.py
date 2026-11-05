"""Criar usuário e definir senha. Usado pelo script de terminal; a rota de administração (etapa 6) reaproveita."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import seguranca
from app.models import Perfil, Usuario
from app.servicos.workflow import ErroDeRegra


def _validar_senha(senha: str):
    if len(senha) < seguranca.SENHA_MINIMA:
        raise ErroDeRegra(f"A senha precisa ter pelo menos {seguranca.SENHA_MINIMA} caracteres")


def achar_por_email(sessao: Session, email: str) -> Usuario | None:
    return sessao.scalars(select(Usuario).where(func.lower(Usuario.email) == email.strip().lower())).first()


def criar_usuario(sessao: Session, nome: str, email: str, perfil: str, senha: str | None = None) -> Usuario:
    """Cria o usuário (o commit é de quem chama). Sem senha, ele só poderá entrar com o Google (etapa 5b)."""
    if senha is not None:
        _validar_senha(senha)
    perfil_db = sessao.scalars(select(Perfil).where(Perfil.nome == perfil)).first()
    if perfil_db is None:
        nomes = [p.nome for p in sessao.scalars(select(Perfil))]
        raise ErroDeRegra(f"Perfil '{perfil}' não existe (use {nomes})")
    if achar_por_email(sessao, email):
        raise ErroDeRegra("Já existe um usuário com esse e-mail", status=409)
    usuario = Usuario(nome=nome.strip(), email=email.strip(), perfil_id=perfil_db.id,
                      senha_hash=seguranca.gerar_hash(senha) if senha else None)
    sessao.add(usuario)
    sessao.flush()
    return usuario


def definir_senha(sessao: Session, email: str, senha: str) -> Usuario:
    _validar_senha(senha)
    usuario = achar_por_email(sessao, email)
    if usuario is None:
        raise ErroDeRegra("Usuário não encontrado", status=404)
    usuario.senha_hash = seguranca.gerar_hash(senha)
    return usuario
