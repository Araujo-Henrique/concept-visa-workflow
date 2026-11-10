"""Teto de tamanho do corpo da requisição, contado nos bytes que realmente chegam.

Por que não basta olhar o cabeçalho Content-Length: quem envia com "Transfer-Encoding: chunked" não tem esse
cabeçalho, e o servidor leria o corpo inteiro na memória antes de qualquer rota decidir. Aqui cada pedaço que a
rota lê é somado; passou do limite, a leitura para com 413. Vale para qualquer forma de enviar o corpo.

É um middleware ASGI puro (e não do tipo `@app.middleware("http")`) porque precisa embrulhar o `receive`, que é por
onde o corpo entra. Fica por dentro dos outros: o 413 sai como qualquer erro de rota, com log e X-Request-ID.
"""
from starlette.exceptions import HTTPException


class CorpoGrandeDemais(HTTPException):
    """HTTPException de propósito: o FastAPI transforma qualquer outro erro de leitura do corpo em 400, mas repassa
    esta, e a resposta sai como 413 {"detail": ...}."""

    def __init__(self):
        super().__init__(status_code=413, detail="Dados grandes demais")


class LimiteDeCorpo:
    def __init__(self, app, limite: int):
        self.app = app
        self.limite = limite

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        total = 0

        async def contando():
            nonlocal total
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                total += len(mensagem.get("body", b""))
                if total > self.limite:
                    raise CorpoGrandeDemais()
            return mensagem

        await self.app(scope, contando, send)
