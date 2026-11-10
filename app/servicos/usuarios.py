"""Criar usuário e definir senha. Usado pelo script de terminal; a rota de administração (etapa 6) reaproveita."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import seguranca
from app.models import AuditoriaUsuario, Perfil, Usuario
from app.servicos.workflow import ErroDeRegra


def _validar_senha(senha: str):
    if len(senha) < seguranca.SENHA_MINIMA:
        raise ErroDeRegra(f"A senha precisa ter pelo menos {seguranca.SENHA_MINIMA} caracteres")


def achar_por_email(sessao: Session, email: str) -> Usuario | None:
    return sessao.scalars(select(Usuario).where(func.lower(Usuario.email) == email.strip().lower())).first()


def criar_usuario(sessao: Session, nome: str, email: str, perfil: str, senha: str | None = None) -> Usuario:
    """Cria o usuário (o commit é de quem chama). Sem senha, ele só entra com o Google (só admin entra com senha)."""
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
    if usuario.perfil.nome != "admin":
        # só admin entra com senha; uma senha definida aqui ficaria "viva" se a pessoa fosse promovida depois
        raise ErroDeRegra("Só administradores têm senha; os demais perfis entram com o Google", status=409)
    usuario.senha_hash = seguranca.gerar_hash(senha)
    usuario.token_version += 1  # sessões abertas com a senha antiga caem
    return usuario


# ---------------------------------------------------------------- administração (etapa 6)

def _registrar(sessao: Session, alvo: Usuario, feito_por: Usuario | None, campo: str, antes, depois):
    sessao.add(AuditoriaUsuario(usuario_id=alvo.id, feito_por_id=feito_por.id if feito_por else None,
                                campo=campo, valor_anterior=None if antes is None else str(antes),
                                valor_novo=None if depois is None else str(depois)))


def _outros_admins_ativos(sessao: Session, alvo: Usuario) -> int:
    return sessao.scalar(
        select(func.count()).select_from(Usuario).join(Perfil)
        .where(Perfil.nome == "admin", Usuario.ativo.is_(True), Usuario.id != alvo.id))


def _travar_administradores(sessao: Session) -> None:
    """Trava (FOR UPDATE) as linhas de todos os administradores até o fim da transação. Sem isto, dois admins que
    rebaixam um ao outro AO MESMO TEMPO contam, cada um, "ainda existe um administrador" (o outro), os dois passam e
    os dois gravam: sobra zero. Com a trava, o segundo espera o primeiro terminar e então conta de verdade."""
    sessao.execute(
        select(Usuario).join(Perfil).where(Perfil.nome == "admin").order_by(Usuario.id)
        .with_for_update(of=Usuario).execution_options(populate_existing=True)).all()


def atualizar_usuario(sessao: Session, alvo: Usuario, feito_por: Usuario, nome: str | None = None,
                      perfil: str | None = None, ativo: bool | None = None) -> Usuario:
    """Muda nome, perfil ou ativo e registra cada mudança na auditoria (o commit é de quem chama).

    Trava: a empresa nunca fica sem um administrador ativo, senão ninguém mais consegue gerenciar usuários."""
    novo_perfil = None
    if perfil is not None and perfil != alvo.perfil.nome:
        novo_perfil = sessao.scalars(select(Perfil).where(Perfil.nome == perfil)).first()
        if novo_perfil is None:
            raise ErroDeRegra(f"Perfil '{perfil}' não existe (use {[p.nome for p in sessao.scalars(select(Perfil))]})")

    if alvo.perfil.nome == "admin":  # pode estar saindo do conjunto de administradores: serializa e relê o estado
        _travar_administradores(sessao)
        sessao.refresh(alvo)
    era_admin_ativo = alvo.perfil.nome == "admin" and alvo.ativo
    sera_admin_ativo = (novo_perfil.nome if novo_perfil else alvo.perfil.nome) == "admin" and \
                       (alvo.ativo if ativo is None else ativo)
    if era_admin_ativo and not sera_admin_ativo and _outros_admins_ativos(sessao, alvo) == 0:
        raise ErroDeRegra("É preciso manter pelo menos um administrador ativo", status=409)

    if novo_perfil is not None:
        _registrar(sessao, alvo, feito_por, "perfil", alvo.perfil.nome, novo_perfil.nome)
        alvo.perfil = novo_perfil
        if novo_perfil.nome != "admin" and alvo.senha_hash is not None:
            # só admin entra com senha: quem deixa de ser admin passa a entrar só com o Google
            alvo.senha_hash = None
            alvo.token_version += 1
            _registrar(sessao, alvo, feito_por, "senha", None, "removida (deixou de ser administrador)")
    if ativo is not None and ativo != alvo.ativo:
        _registrar(sessao, alvo, feito_por, "ativo", alvo.ativo, ativo)
        alvo.ativo = ativo
        if not ativo:
            alvo.token_version += 1  # reativar depois não ressuscita os tokens de antes
    if nome is not None and nome.strip() != alvo.nome:
        _registrar(sessao, alvo, feito_por, "nome", alvo.nome, nome.strip())
        alvo.nome = nome.strip()
    return alvo


def redefinir_senha(sessao: Session, alvo: Usuario, feito_por: Usuario, nova: str) -> Usuario:
    """Admin define a senha de outro usuário. A auditoria guarda só que houve a troca, nunca a senha."""
    _validar_senha(nova)
    alvo.senha_hash = seguranca.gerar_hash(nova)
    alvo.token_version += 1  # quem estava logado com a senha antiga precisa entrar de novo
    _registrar(sessao, alvo, feito_por, "senha", None, "redefinida")
    return alvo


def trocar_propria_senha(sessao: Session, usuario: Usuario, atual: str, nova: str) -> Usuario:
    if usuario.senha_hash is None or not seguranca.verificar(atual, usuario.senha_hash):
        raise ErroDeRegra("Senha atual incorreta")
    _validar_senha(nova)
    usuario.senha_hash = seguranca.gerar_hash(nova)
    usuario.token_version += 1  # derruba as outras sessões; a rota devolve um token novo para esta
    _registrar(sessao, usuario, usuario, "senha", None, "trocada pelo próprio usuário")
    return usuario
