"""Administração de usuários. Só quem tem a permissão `administrar` (perfil admin) entra aqui."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.idempotencia import RotaIdempotente
from app.deps import Sessao, UsuarioAtual, exige
from app.models import AuditoriaUsuario, Perfil, Usuario
from app.permissoes import ADMINISTRAR
from app.routers.comum import obter_ou_404
from app.schemas.auth import UsuarioOut
from app.schemas.usuario import AuditoriaOut, NovaSenha, UsuarioNovo, UsuarioUpdate
from app.servicos import usuarios as servico
from app.servicos.workflow import ErroDeRegra

router = APIRouter(prefix="/usuarios", tags=["Usuários (admin)"], dependencies=[Depends(exige(ADMINISTRAR))],
                   route_class=RotaIdempotente)


def _traduz(erro: ErroDeRegra) -> HTTPException:
    return HTTPException(status_code=erro.status, detail=erro.mensagem)


@router.get("", response_model=list[UsuarioOut])
def listar(sessao: Sessao, ativo: bool | None = None, perfil: str | None = None):
    consulta = select(Usuario).order_by(Usuario.id)
    if ativo is not None:
        consulta = consulta.where(Usuario.ativo == ativo)
    if perfil:
        consulta = consulta.join(Perfil).where(Perfil.nome == perfil)
    return [UsuarioOut.de(u) for u in sessao.scalars(consulta)]


SO_ADMIN_TEM_SENHA = "Só administradores têm senha; os demais perfis entram com o Google"


@router.post("", response_model=UsuarioOut, status_code=201)
def criar(dados: UsuarioNovo, sessao: Sessao, admin: UsuarioAtual):
    if dados.senha and dados.perfil != "admin":
        raise HTTPException(status_code=422, detail=SO_ADMIN_TEM_SENHA)
    try:
        usuario = servico.criar_usuario(sessao, dados.nome, dados.email, dados.perfil, dados.senha)
    except ErroDeRegra as erro:
        raise _traduz(erro)
    servico._registrar(sessao, usuario, admin, "criado", None, dados.perfil)
    sessao.commit()
    return UsuarioOut.de(usuario)


@router.get("/{usuario_id}", response_model=UsuarioOut)
def obter(usuario_id: int, sessao: Sessao):
    return UsuarioOut.de(obter_ou_404(sessao, Usuario, usuario_id, "Usuário"))


@router.patch("/{usuario_id}", response_model=UsuarioOut)
def atualizar(usuario_id: int, dados: UsuarioUpdate, sessao: Sessao, admin: UsuarioAtual):
    alvo = obter_ou_404(sessao, Usuario, usuario_id, "Usuário")
    campos = dados.model_dump(exclude_unset=True)
    if any(valor is None for valor in campos.values()):
        raise HTTPException(status_code=422, detail="Os campos informados não podem ser vazios")
    try:
        servico.atualizar_usuario(sessao, alvo, admin, **campos)
    except ErroDeRegra as erro:
        raise _traduz(erro)
    sessao.commit()
    return UsuarioOut.de(alvo)


@router.post("/{usuario_id}/senha", status_code=204)
def redefinir_senha(usuario_id: int, dados: NovaSenha, sessao: Sessao, admin: UsuarioAtual):
    alvo = obter_ou_404(sessao, Usuario, usuario_id, "Usuário")
    if alvo.id == admin.id:
        # a troca da própria senha exige a senha atual (e conta as tentativas erradas): quem pegou um computador
        # logado não pode contornar isso por aqui
        raise HTTPException(status_code=409, detail="Para trocar a sua própria senha use 'Minha conta' (pede a senha atual)")
    if alvo.perfil.nome != "admin":
        raise HTTPException(status_code=409, detail=SO_ADMIN_TEM_SENHA)
    try:
        servico.redefinir_senha(sessao, alvo, admin, dados.senha)
    except ErroDeRegra as erro:
        raise _traduz(erro)
    sessao.commit()


@router.get("/{usuario_id}/auditoria", response_model=list[AuditoriaOut])
def auditoria(usuario_id: int, sessao: Sessao):
    obter_ou_404(sessao, Usuario, usuario_id, "Usuário")
    linhas = sessao.scalars(select(AuditoriaUsuario).where(AuditoriaUsuario.usuario_id == usuario_id)
                            .order_by(AuditoriaUsuario.id))
    return [AuditoriaOut.model_validate(a) for a in linhas]
