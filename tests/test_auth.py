from datetime import timedelta

import jwt
import pytest
from sqlalchemy import select

from app import seguranca
from app.models import Evento, Processo, Usuario
from app.servicos.usuarios import criar_usuario, definir_senha
from app.servicos.workflow import ErroDeRegra
from tests.conftest import SENHA_TESTE
from tests.test_api import novo_cliente, novo_obt


def login(c, email="teste@exemplo.com", senha=SENHA_TESTE):
    return c.post("/auth/login", json={"email": email, "senha": senha})


# ---------------------------------------------------------------- login

def test_login_correto_devolve_token_que_identifica_o_usuario(client_anonimo, usuario_teste):
    resposta = login(client_anonimo)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer" and corpo["expira_em_minutos"] == 30
    eu = client_anonimo.get("/auth/eu", headers={"Authorization": f"Bearer {corpo['access_token']}"})
    assert eu.status_code == 200
    assert eu.json() == {"id": usuario_teste.id, "nome": "Usuario Teste", "email": "teste@exemplo.com",
                         "ativo": True, "perfil": "admin"}
    assert "senha_hash" not in eu.json()


def test_login_ignora_maiusculas_no_email(client_anonimo, usuario_teste):
    assert login(client_anonimo, email="TESTE@Exemplo.COM").status_code == 200


def test_senha_errada_e_email_inexistente_dao_a_mesma_resposta(client_anonimo, usuario_teste):
    errada = login(client_anonimo, senha="outra-senha-qualquer")
    inexistente = login(client_anonimo, email="ninguem@exemplo.com")
    assert errada.status_code == inexistente.status_code == 401
    assert errada.json() == inexistente.json()  # não revela se o e-mail existe


def test_usuario_inativo_nao_chega_a_conferir_a_senha(client_anonimo, usuario_teste, sessao, monkeypatch):
    usuario_teste.ativo = False
    sessao.commit()
    conferidos = []
    original = seguranca.verificar
    monkeypatch.setattr(seguranca, "verificar", lambda senha, hash_: conferidos.append(hash_) or original(senha, hash_))
    resposta = login(client_anonimo)  # senha CERTA, mas o usuário está inativo
    assert resposta.status_code == 401
    assert usuario_teste.senha_hash not in conferidos  # o hash real nunca foi usado
    assert conferidos == [seguranca.HASH_FALSO]  # só o hash falso, para igualar o tempo de resposta


def test_usuario_so_google_nao_entra_com_senha(client_anonimo, sessao):
    criar_usuario(sessao, "So Google", "google@exemplo.com", "leitor", senha=None)
    sessao.commit()
    assert login(client_anonimo, email="google@exemplo.com", senha="qualquer-coisa-123").status_code == 401


def test_login_nao_aceita_campos_extras(client_anonimo):
    assert client_anonimo.post("/auth/login", json={"email": "a@b.com", "senha": "x", "perfil": "admin"}).status_code == 422


# ---------------------------------------------------------------- proteção das rotas

ROTAS = [("get", "/clientes"), ("post", "/clientes"), ("get", "/painel"), ("get", "/processos-obt"),
         ("get", "/processos-ren"), ("get", "/processos-pass"), ("post", "/processos/1/situacao"),
         ("get", "/processos/1/eventos"), ("post", "/processos/1/solicitantes"), ("get", "/auth/eu")]


@pytest.mark.parametrize("metodo,caminho", ROTAS)
def test_rotas_exigem_token(client_anonimo, metodo, caminho):
    resposta = getattr(client_anonimo, metodo)(caminho)
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


def test_token_invalido_adulterado_ou_expirado_da_401(client_anonimo, usuario_teste):
    def com(token):
        return client_anonimo.get("/clientes", headers={"Authorization": f"Bearer {token}"})

    assert com("lixo").status_code == 401
    assert com(seguranca.criar_token(usuario_teste.id, validade=timedelta(seconds=-5))).status_code == 401  # expirado
    assert com(jwt.encode({"sub": str(usuario_teste.id), "exp": 9999999999}, "outro-segredo-diferente-de-32-caracteres!!",
                          algorithm="HS256")).status_code == 401  # assinado com outro segredo
    sem_assinatura = jwt.encode({"sub": str(usuario_teste.id), "exp": 9999999999}, key=None, algorithm="none")
    assert com(sem_assinatura).status_code == 401  # ataque "alg: none"
    assert com(jwt.encode({"exp": 9999999999}, seguranca._segredo(), algorithm="HS256")).status_code == 401  # sem sub
    assert com(seguranca.criar_token(usuario_teste.id)).status_code == 200  # o válido segue funcionando


def test_desativar_o_usuario_corta_o_acesso_na_hora_mesmo_com_token_valido(client, usuario_teste, sessao):
    assert client.get("/clientes").status_code == 200
    usuario_teste.ativo = False
    sessao.commit()
    resposta = client.get("/clientes")  # mesmo token, ainda dentro da validade
    assert resposta.status_code == 403 and resposta.json()["detail"] == "Acesso desativado"
    usuario_teste.ativo = True
    sessao.commit()
    assert client.get("/clientes").status_code == 200


def test_usuario_removido_perde_o_acesso(client, usuario_teste, sessao):
    sessao.delete(usuario_teste)
    sessao.commit()
    assert client.get("/clientes").status_code == 401


def test_mudar_o_perfil_vale_na_proxima_requisicao(client, usuario_teste, sessao):
    assert client.get("/auth/eu").json()["perfil"] == "admin"
    from app.models import Perfil
    usuario_teste.perfil_id = sessao.scalars(select(Perfil).where(Perfil.nome == "leitor")).one().id
    sessao.commit()
    assert client.get("/auth/eu").json()["perfil"] == "leitor"  # o token não guarda o perfil


# ---------------------------------------------------------------- autoria

def test_processo_e_eventos_registram_quem_fez(client, usuario_teste, sessao):
    cliente = novo_cliente(client)
    processo = novo_obt(client, cliente["id"])
    client.post(f"/processos/{processo['id']}/situacao", json={"situacao": "Pago"})
    assert sessao.get(Processo, processo["id"]).criado_por_id == usuario_teste.id
    eventos = sessao.scalars(select(Evento).order_by(Evento.id)).all()
    assert [e.usuario_id for e in eventos] == [usuario_teste.id, usuario_teste.id]
    assert [e.tipo.value for e in eventos] == ["criado", "situacao_alterada"]


# ---------------------------------------------------------------- segurança da senha e do segredo

def test_senha_vira_hash_com_sal_e_nunca_fica_em_texto(sessao):
    a = criar_usuario(sessao, "A", "a@exemplo.com", "leitor", "mesma-senha-123")
    b = criar_usuario(sessao, "B", "b@exemplo.com", "leitor", "mesma-senha-123")
    assert "mesma-senha-123" not in a.senha_hash and a.senha_hash.startswith("$argon2")
    assert a.senha_hash != b.senha_hash  # o sal faz hashes diferentes para a mesma senha
    assert seguranca.verificar("mesma-senha-123", a.senha_hash)
    assert not seguranca.verificar("mesma-senha-124", a.senha_hash)


def test_regras_de_criacao_de_usuario(sessao):
    with pytest.raises(ErroDeRegra, match="pelo menos 10"):
        criar_usuario(sessao, "A", "a@exemplo.com", "leitor", "curta")
    with pytest.raises(ErroDeRegra, match="Perfil 'chefe' não existe"):
        criar_usuario(sessao, "A", "a@exemplo.com", "chefe", "senha-longa-123")
    criar_usuario(sessao, "A", "a@exemplo.com", "leitor", "senha-longa-123")
    with pytest.raises(ErroDeRegra) as erro:
        criar_usuario(sessao, "Outra", "A@EXEMPLO.com", "leitor", "senha-longa-123")  # e-mail repetido
    assert erro.value.status == 409


def test_definir_senha_troca_o_hash_e_permite_entrar(client_anonimo, sessao):
    criar_usuario(sessao, "Importado", "importado@exemplo.com", "atendente", senha=None)  # veio da importação
    sessao.commit()
    assert login(client_anonimo, "importado@exemplo.com", "nova-senha-segura-1").status_code == 401
    definir_senha(sessao, "importado@exemplo.com", "nova-senha-segura-1")
    sessao.commit()
    assert login(client_anonimo, "importado@exemplo.com", "nova-senha-segura-1").status_code == 200
    with pytest.raises(ErroDeRegra, match="não encontrado"):
        definir_senha(sessao, "ninguem@exemplo.com", "nova-senha-segura-1")


def test_sem_segredo_configurado_a_api_se_recusa_a_emitir_token(monkeypatch):
    monkeypatch.delenv("JWT_SECRET")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        seguranca.criar_token(1)
    monkeypatch.setenv("JWT_SECRET", "curto")
    with pytest.raises(RuntimeError, match="32 caracteres"):
        seguranca.criar_token(1)


# ---------------------------------------------------------------- renovação (sessão deslizante)

def _renovar(c, token):
    return c.post("/auth/renovar", headers={"Authorization": f"Bearer {token}"})


def _corpo(token):
    return jwt.decode(token, seguranca._segredo(), algorithms=["HS256"])


def test_renovar_troca_o_token_mantendo_a_hora_do_login(client_anonimo, usuario_teste):
    from datetime import datetime, timezone
    login_ha_2h = datetime.now(timezone.utc) - timedelta(hours=2)
    antigo = seguranca.criar_token(usuario_teste.id, validade=timedelta(minutes=3), inicio=login_ha_2h)
    resposta = _renovar(client_anonimo, antigo)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["expira_em_minutos"] == 30
    novo = _corpo(corpo["access_token"])
    assert novo["ini"] == int(login_ha_2h.timestamp()) and novo["sub"] == str(usuario_teste.id)
    assert novo["exp"] > _corpo(antigo)["exp"]
    assert client_anonimo.get("/auth/eu", headers={"Authorization": f"Bearer {corpo['access_token']}"}).status_code == 200


def test_renovar_respeita_o_teto_da_sessao(client_anonimo, usuario_teste, monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setenv("JWT_SESSAO_MAXIMA_HORAS", "10")
    agora = datetime.now(timezone.utc)
    # faltam 10 minutos para o teto: o novo vale só até ele, não 30 minutos
    quase = seguranca.criar_token(usuario_teste.id, inicio=agora - timedelta(hours=9, minutes=50))
    resposta = _renovar(client_anonimo, quase)
    assert resposta.status_code == 200 and resposta.json()["expira_em_minutos"] in (9, 10)
    # faltam 30 segundos para o teto (o token ainda vale): não renova, só entrando de novo
    no_limite = seguranca.criar_token(usuario_teste.id, inicio=agora - timedelta(hours=9, minutes=59, seconds=30))
    resposta = _renovar(client_anonimo, no_limite)
    assert resposta.status_code == 401 and "limite" in resposta.json()["detail"]


def test_token_novo_ja_nasce_dentro_do_teto(usuario_teste, monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setenv("JWT_SESSAO_MAXIMA_HORAS", "1")
    corpo = _corpo(seguranca.criar_token(usuario_teste.id, validade=timedelta(hours=5)))
    assert corpo["exp"] - corpo["ini"] <= 3600
    assert corpo["exp"] <= datetime.now(timezone.utc).timestamp() + 3601


def test_renovar_exige_token_valido_e_usuario_ativo(client_anonimo, usuario_teste, sessao):
    assert client_anonimo.post("/auth/renovar").status_code == 401
    assert _renovar(client_anonimo, "lixo").status_code == 401
    vencido = seguranca.criar_token(usuario_teste.id, validade=timedelta(seconds=-5))
    assert _renovar(client_anonimo, vencido).status_code == 401
    valido = seguranca.criar_token(usuario_teste.id)
    usuario_teste.ativo = False
    sessao.commit()
    assert _renovar(client_anonimo, valido).status_code == 403
    usuario_teste.ativo = True
    sessao.commit()


def test_token_antigo_sem_ini_renova_contando_do_iat(client_anonimo, usuario_teste):
    from datetime import datetime, timezone
    agora = datetime.now(timezone.utc)
    antigo = jwt.encode({"sub": str(usuario_teste.id), "iat": agora, "exp": agora + timedelta(minutes=5)},
                        seguranca._segredo(), algorithm="HS256")
    resposta = _renovar(client_anonimo, antigo)
    assert resposta.status_code == 200
    assert _corpo(resposta.json()["access_token"])["ini"] == int(agora.timestamp())
