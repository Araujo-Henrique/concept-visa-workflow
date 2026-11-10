"""Login com o Google. Nada aqui fala com o Google de verdade: o id_token é assinado com uma chave RSA criada no
teste e as chamadas de rede são trocadas por dobles."""
import io
import json
import time
import urllib.error

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import func, select

from app import google, limites
from app.models import Usuario
from app.servicos.usuarios import criar_usuario

CLIENT_ID = "123456-teste.apps.googleusercontent.com"
SEGREDO_DO_CLIENTE = "segredo-falso-do-cliente-so-para-teste"  # de propósito fora do formato das chaves reais do Google (o GitHub barra o push)
NONCE = "nonce-de-teste-com-mais-de-16-caracteres"
VERIFICADOR = "v" * 43
REDIRECT = "http://localhost:3000/api/auth/google/callback"
CORPO = {"code": "codigo-do-google", "code_verifier": VERIFICADOR, "nonce": NONCE, "redirect_uri": REDIRECT}


@pytest.fixture(autouse=True)
def ambiente_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", SEGREDO_DO_CLIENTE)
    monkeypatch.delenv("GOOGLE_ALLOWED_DOMAIN", raising=False)


@pytest.fixture(scope="module")
def chave():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def google_falso(monkeypatch, chave):
    """As chaves públicas do Google passam a ser a do teste (sem rede)."""
    class Chaves:
        def get_signing_key_from_jwt(self, token):
            class Assinatura:
                key = chave.public_key()
            return Assinatura()
    monkeypatch.setattr(google, "_cliente_de_chaves", lambda: Chaves())


def id_token(chave, **mudancas):
    agora = int(time.time())
    corpo = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "1122334455", "iat": agora,
             "exp": agora + 300, "email": "ana@exemplo.com", "email_verified": True, "name": "Ana Souza",
             "nonce": NONCE, **mudancas}
    corpo = {k: v for k, v in corpo.items() if v is not None}
    return jwt.encode(corpo, chave, algorithm="RS256")


# ---------------------------------------------------------------- conferência do id_token

def test_id_token_valido_devolve_email_e_nome(google_falso, chave):
    assert google.validar_id_token(id_token(chave), NONCE) == {"email": "ana@exemplo.com", "nome": "Ana Souza"}


def test_emissor_antigo_do_google_tambem_vale(google_falso, chave):
    assert google.validar_id_token(id_token(chave, iss="accounts.google.com"), NONCE)["email"] == "ana@exemplo.com"


@pytest.mark.parametrize("mudanca,motivo", [
    ({"aud": "outro-app.apps.googleusercontent.com"}, "id_token inválido"),  # token feito para outro app
    ({"iss": "https://falso.exemplo.com"}, "id_token inválido"),
    ({"exp": int(time.time()) - 600}, "id_token inválido"),  # vencido
    ({"nonce": "outro-nonce-qualquer-aqui"}, "nonce"),  # id_token de outro login
    ({"nonce": None}, "nonce"),
    ({"email_verified": False}, "não verificado"),
    ({"email_verified": "true"}, "não verificado"),  # só o booleano verdadeiro vale
    ({"email": None}, "não verificado"),
    ({"sub": None}, "id_token inválido"),
])
def test_id_token_com_problema_e_recusado(google_falso, chave, mudanca, motivo):
    with pytest.raises(google.ErroGoogle, match=motivo):
        google.validar_id_token(id_token(chave, **mudanca), NONCE)


def test_assinatura_de_outra_chave_e_recusada(google_falso):
    outra = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(google.ErroGoogle, match="inválido"):
        google.validar_id_token(id_token(outra), NONCE)


def test_token_sem_assinatura_ou_com_algoritmo_trocado_e_recusado(google_falso, chave):
    agora = int(time.time())
    corpo = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "1", "iat": agora, "exp": agora + 300,
             "email": "ana@exemplo.com", "email_verified": True, "nonce": NONCE}
    sem_assinatura = jwt.encode(corpo, key=None, algorithm="none")
    com_hmac = jwt.encode(corpo, "segredo-qualquer-com-mais-de-32-caracteres-aqui", algorithm="HS256")
    for forjado in (sem_assinatura, com_hmac, "isto-nao-e-um-jwt"):
        with pytest.raises(google.ErroGoogle):
            google.validar_id_token(forjado, NONCE)


def test_dominio_permitido_so_aceita_o_dominio_configurado(google_falso, chave, monkeypatch):
    monkeypatch.setenv("GOOGLE_ALLOWED_DOMAIN", "@Exemplo.com")
    assert google.validar_id_token(id_token(chave), NONCE)["email"] == "ana@exemplo.com"
    with pytest.raises(google.ErroGoogle, match="domínio"):
        google.validar_id_token(id_token(chave, email="ana@gmail.com"), NONCE)
    with pytest.raises(google.ErroGoogle, match="domínio"):  # o truque do subdomínio/sufixo
        google.validar_id_token(id_token(chave, email="ana@exemplo.com.golpe.net"), NONCE)


def test_sem_client_id_configurado_nada_e_aceito(chave, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID")
    with pytest.raises(google.ErroGoogle, match="não configurado"):
        google.validar_id_token(id_token(chave), NONCE)


# ---------------------------------------------------------------- troca do código (rede simulada)

class Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_troca_manda_os_campos_certos_e_devolve_o_id_token(monkeypatch):
    enviados = {}

    def falso(pedido, timeout):
        enviados["url"], enviados["corpo"], enviados["timeout"] = pedido.full_url, pedido.data.decode(), timeout
        return Resposta(json.dumps({"id_token": "o.id.token", "access_token": "nao-usamos"}).encode())

    monkeypatch.setattr(google.urllib.request, "urlopen", falso)
    assert google.trocar_codigo("codigo-1", VERIFICADOR, REDIRECT) == "o.id.token"
    assert enviados["url"] == google.URL_TOKEN and enviados["timeout"] == google.TEMPO_LIMITE
    for trecho in ("code=codigo-1", "grant_type=authorization_code", f"code_verifier={VERIFICADOR}",
                   "redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fapi%2Fauth%2Fgoogle%2Fcallback"):
        assert trecho in enviados["corpo"]


def test_google_recusando_o_codigo_vira_erro_sem_vazar_o_segredo(monkeypatch):
    def falso(pedido, timeout):
        raise urllib.error.HTTPError(google.URL_TOKEN, 400, "Bad Request", {},
                                     io.BytesIO(b'{"error": "invalid_grant"}'))

    monkeypatch.setattr(google.urllib.request, "urlopen", falso)
    with pytest.raises(google.ErroGoogle) as erro:
        google.trocar_codigo("velho", VERIFICADOR, REDIRECT)
    assert "invalid_grant" in erro.value.motivo and SEGREDO_DO_CLIENTE not in erro.value.motivo


@pytest.mark.parametrize("falha", [urllib.error.URLError("sem rede"), TimeoutError()])
def test_google_fora_do_ar_vira_erro(monkeypatch, falha):
    def falso(pedido, timeout):
        raise falha

    monkeypatch.setattr(google.urllib.request, "urlopen", falso)
    with pytest.raises(google.ErroGoogle, match="não consegui falar"):
        google.trocar_codigo("c", VERIFICADOR, REDIRECT)


def test_resposta_sem_id_token_e_erro(monkeypatch):
    monkeypatch.setattr(google.urllib.request, "urlopen", lambda p, timeout: Resposta(b'{"access_token": "x"}'))
    with pytest.raises(google.ErroGoogle, match="sem id_token"):
        google.trocar_codigo("c", VERIFICADOR, REDIRECT)


def test_sem_credenciais_nem_tenta_falar_com_o_google(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET")
    chamadas = []
    monkeypatch.setattr(google.urllib.request, "urlopen", lambda *a, **k: chamadas.append(a))
    with pytest.raises(google.ErroGoogle, match="não configurados"):
        google.trocar_codigo("c", VERIFICADOR, REDIRECT)
    assert chamadas == []


# ---------------------------------------------------------------- rotas

@pytest.fixture
def google_responde(monkeypatch):
    """Faz o Google 'responder' com a identidade pedida pelo teste (a conferência real está acima)."""
    def configurar(email="ana@exemplo.com", nome="Ana Souza"):
        monkeypatch.setattr(google, "trocar_codigo", lambda codigo, verificador, uri: "id-token-falso")
        monkeypatch.setattr(google, "validar_id_token", lambda token, nonce: {"email": email, "nome": nome})
    return configurar


def _entrar(c, **mudancas):
    return c.post("/auth/google", json={**CORPO, **mudancas})


def test_cadastrado_entra_so_com_o_google_sem_ter_senha(client_anonimo, sessao, google_responde):
    criar_usuario(sessao, "Ana Souza", "ana@exemplo.com", "atendente", senha=None)
    sessao.commit()
    google_responde()
    resposta = _entrar(client_anonimo)
    assert resposta.status_code == 200
    token = resposta.json()["access_token"]
    eu = client_anonimo.get("/auth/eu", headers={"Authorization": f"Bearer {token}"}).json()
    assert eu["email"] == "ana@exemplo.com" and eu["perfil"] == "atendente"


def test_o_e_mail_do_google_nao_diferencia_maiusculas(client_anonimo, sessao, google_responde):
    criar_usuario(sessao, "Ana", "ana@exemplo.com", "leitor", senha=None)
    sessao.commit()
    google_responde(email="Ana@Exemplo.COM")
    assert _entrar(client_anonimo).status_code == 200


def test_o_perfil_vem_do_cadastro_e_nao_do_google(client_anonimo, sessao, google_responde):
    criar_usuario(sessao, "Ana", "ana@exemplo.com", "leitor", senha=None)
    sessao.commit()
    google_responde(nome="Ana Administradora")
    token = _entrar(client_anonimo).json()["access_token"]
    eu = client_anonimo.get("/auth/eu", headers={"Authorization": f"Bearer {token}"}).json()
    assert eu["perfil"] == "leitor" and eu["nome"] == "Ana"  # nem o nome do Google sobrescreve o cadastro


def test_email_fora_do_cadastro_nao_entra_e_nada_e_criado(client_anonimo, sessao, usuario_teste, google_responde):
    google_responde(email="estranho@gmail.com")
    antes = sessao.scalar(select(func.count()).select_from(Usuario))
    resposta = _entrar(client_anonimo)
    assert resposta.status_code == 403 and "não tem acesso" in resposta.json()["detail"]
    assert "access_token" not in resposta.text
    sessao.expire_all()
    assert sessao.scalar(select(func.count()).select_from(Usuario)) == antes


def test_usuario_desativado_nao_entra(client_anonimo, sessao, google_responde):
    criar_usuario(sessao, "Ana", "ana@exemplo.com", "atendente", senha=None).ativo = False
    sessao.commit()
    google_responde()
    assert _entrar(client_anonimo).status_code == 403


def test_google_recusando_da_401_generico_sem_o_motivo(client_anonimo, monkeypatch):
    def recusa(*args):
        raise google.ErroGoogle("invalid_grant: segredo interno que não vai para a tela")

    monkeypatch.setattr(google, "trocar_codigo", recusa)
    resposta = _entrar(client_anonimo)
    assert resposta.status_code == 401
    assert resposta.json() == {"detail": "Não foi possível confirmar o login com o Google"}


def test_corpo_invalido_da_422_antes_de_falar_com_o_google(client_anonimo, monkeypatch):
    chamadas = []
    monkeypatch.setattr(google, "trocar_codigo", lambda *a: chamadas.append(a))
    assert _entrar(client_anonimo, code_verifier="curto").status_code == 422  # PKCE: 43 a 128 caracteres
    assert _entrar(client_anonimo, nonce="curto").status_code == 422
    assert _entrar(client_anonimo, code="").status_code == 422
    assert client_anonimo.post("/auth/google", json={**CORPO, "perfil": "admin"}).status_code == 422
    assert chamadas == []


def test_tentativas_do_google_tambem_tem_limite_por_ip(client_anonimo, monkeypatch):
    def recusa(*args):
        raise google.ErroGoogle("x")

    monkeypatch.setattr(google, "trocar_codigo", recusa)
    assert [_entrar(client_anonimo).status_code for _ in range(10)] == [401] * 10
    bloqueado = _entrar(client_anonimo)
    assert bloqueado.status_code == 429 and bloqueado.headers["retry-after"]
    limites.zerar_tudo()


def test_falha_e_sucesso_vao_para_o_log_sem_o_email_inteiro(client_anonimo, sessao, google_responde, caplog):
    criar_usuario(sessao, "Ana", "ana@exemplo.com", "atendente", senha=None)
    sessao.commit()
    with caplog.at_level("INFO", logger="concept.acesso"):
        google_responde()
        _entrar(client_anonimo)
        google_responde(email="intruso@gmail.com")
        _entrar(client_anonimo)
    assert "login Google: a***@exemplo.com" in caplog.text
    assert "login Google sem acesso: i***@gmail.com não cadastrado" in caplog.text
    assert "ana@exemplo.com" not in caplog.text and "intruso@gmail.com" not in caplog.text


def test_config_publica_so_traz_o_id_do_cliente(client_anonimo):
    resposta = client_anonimo.get("/auth/google/config")
    assert resposta.status_code == 200 and resposta.json() == {"client_id": CLIENT_ID}
    assert SEGREDO_DO_CLIENTE not in resposta.text


def test_config_sem_credenciais_da_503(client_anonimo, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET")
    assert client_anonimo.get("/auth/google/config").status_code == 503
