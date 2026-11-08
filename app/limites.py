"""Limites de requisições: protegem a API e o banco de abuso (robô testando senhas, alguém martelando a API).

Duas peças:
  - `Janela`: conta quantas vezes uma chave (IP, e-mail...) aparece numa janela de tempo deslizante;
  - `ip_do_cliente`: quem está do outro lado. Quem chama a API é o servidor do Next, então o IP da conexão é
    sempre o dele (127.0.0.1). O Next repassa o IP de quem abriu o site no cabeçalho X-Cliente-IP, e a API só
    acredita nesse cabeçalho quando a conexão vem de um endereço confiável (API_PROXIES_CONFIAVEIS, padrão: a
    própria máquina). Assim ninguém de fora inventa um IP para escapar do limite.

A contagem fica na memória do processo: basta para um servidor com um processo só (o nosso caso). Com vários
processos ou servidores, cada um contaria por si e o limite real seria multiplicado; aí o lugar é o Redis.
"""
import math
import os
import threading
import time
from collections import deque

from fastapi import Request

CABECALHO_IP = "x-cliente-ip"


class Janela:
    """Janela deslizante: `registrar` devolve 0 se a chave ainda cabe no limite, ou quantos segundos faltam
    para caber de novo."""

    def __init__(self, maximo: int, segundos: float, relogio=time.monotonic):
        self.maximo = maximo
        self.segundos = segundos
        self._relogio = relogio
        self._marcas: dict[str, deque[float]] = {}
        self._trava = threading.Lock()  # as rotas síncronas do FastAPI rodam em várias threads
        self._limpeza = 0.0

    def _podar(self, marcas: deque[float], agora: float) -> None:
        while marcas and marcas[0] <= agora - self.segundos:
            marcas.popleft()

    def _limpar_velhas(self, agora: float) -> None:
        # de tempos em tempos, esquece as chaves paradas (senão o dicionário só cresce)
        if agora - self._limpeza < self.segundos:
            return
        self._limpeza = agora
        for chave in [c for c, m in self._marcas.items() if not m or m[-1] <= agora - self.segundos]:
            del self._marcas[chave]

    def espera(self, chave: str) -> int:
        """Segundos até a chave caber de novo (0 = cabe), sem contar uma tentativa."""
        with self._trava:
            agora = self._relogio()
            marcas = self._marcas.get(chave)
            if not marcas:
                return 0
            self._podar(marcas, agora)
            if len(marcas) < self.maximo:
                return 0
            return max(1, math.ceil(marcas[0] + self.segundos - agora))

    def registrar(self, chave: str) -> int:
        """Conta uma vez. Devolve 0 se coube; senão os segundos de espera (e não conta)."""
        with self._trava:
            agora = self._relogio()
            self._limpar_velhas(agora)
            marcas = self._marcas.setdefault(chave, deque())
            self._podar(marcas, agora)
            if len(marcas) >= self.maximo:
                return max(1, math.ceil(marcas[0] + self.segundos - agora))
            marcas.append(agora)
            return 0

    def esquecer(self, chave: str) -> None:
        with self._trava:
            self._marcas.pop(chave, None)

    def zerar(self) -> None:
        with self._trava:
            self._marcas.clear()


def _inteiro(nome: str, padrao: int) -> int:
    return int(os.environ.get(nome, str(padrao)))


def proxies_confiaveis() -> set[str]:
    valor = os.environ.get("API_PROXIES_CONFIAVEIS", "127.0.0.1,::1")
    return {ip.strip() for ip in valor.split(",") if ip.strip()}


def ip_do_cliente(request: Request) -> str:
    conexao = request.client.host if request.client else "desconhecido"
    repassado = request.headers.get(CABECALHO_IP, "").strip()
    if repassado and conexao in proxies_confiaveis():
        return repassado[:64]
    return conexao


def mensagem_de_espera(segundos: int) -> str:
    if segundos < 60:
        return f"Muitas tentativas. Tente de novo em {segundos} segundos"
    minutos = math.ceil(segundos / 60)
    return f"Muitas tentativas. Tente de novo em {minutos} minuto{'s' if minutos > 1 else ''}"


# Todas as requisições, por IP (um escritório inteiro pode sair pelo mesmo IP: o limite é folgado).
geral = Janela(_inteiro("LIMITE_REQUISICOES_POR_MINUTO", 600), 60)
# Tentativas de login por IP, certas ou erradas: freia o robô que testa muitos e-mails.
login_por_ip = Janela(_inteiro("LIMITE_LOGIN_POR_MINUTO", 10), 60)
# Senhas erradas por conta: depois de N em 15 minutos, a conta fica travada até a mais antiga sair da janela.
falhas_por_conta = Janela(_inteiro("LIMITE_FALHAS_DE_SENHA", 5), 15 * 60)


def zerar_tudo() -> None:
    """Para os testes: cada teste começa sem contagem."""
    for janela in (geral, login_por_ip, falhas_por_conta):
        janela.zerar()
