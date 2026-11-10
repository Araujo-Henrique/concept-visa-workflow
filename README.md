# Concept Visa Workflow

Sistema de acompanhamento do fluxo de processos de visto (obtenção, renovação e passaporte), com histórico
de situações, usuários e perfis. Projeto 2 trilha de estudos; veja [docs/PLANO.md](docs/PLANO.md) para o plano
e as regras, e [docs/DER.md](docs/DER.md) para o diagrama das tabelas.

> Todos os dados de exemplo deste repositório são fictícios.

## Stack
Python 3.14, SQLAlchemy 2.0 (ORM), Alembic (migrations), PostgreSQL, FastAPI, pytest. Front: Next.js (pasta `web/`).
CI: GitHub Actions.

## Mesma base de código, duas máquinas
Só o `.env` e o banco mudam; nada específico de máquina fica no código.

| | Máquina de testes | Máquina real |
|---|---|---|
| Banco | `concept_visa_workflow` (+ `_test`) | `concept_visa_workflow` |
| Dados | seed fictício (`python -m scripts.seed_ficticio`) | importados localmente, fora do repositório |
| Migrations | `alembic upgrade head` | `alembic upgrade head` |

A migration base cria só a estrutura e os dados de referência (perfis e situações).

## Como rodar
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # preencha DATABASE_URL (senha com @ vira %40)
alembic upgrade head          # cria/atualiza as tabelas
```

## Testes
Rodam num banco só de testes (o nome precisa terminar em `_test`; qualquer outro é recusado) e recriam o
esquema pelas migrations, então também provam que as migrations criam o que os modelos esperam.
```
pytest                                                    # backend
pytest --cov=app --cov-branch --cov-report=term-missing   # com cobertura (linhas e ramos)
cd web && npm test                                        # front: Prettier, ESLint, tipos e Jest
cd web && npm run test:e2e                                # ponta a ponta (precisa da API ligada e de API_URL)
```

**Como saber se os testes valem alguma coisa.** Passar não basta. A cobertura mostra o que nenhum teste executa
(backend em torno de 89%, e o que falta é sobretudo leitura de configuração e scripts de terminal). Para saber se
os testes *percebem* um defeito, as regras críticas foram quebradas de propósito, uma por vez (atendente
apagando, usuário desativado entrando, trava do último admin, `FOR UPDATE`, login sem conferir a senha, token
expirado valendo...). Todas as mutações são pegas por algum teste. Duas só foram pegas depois de um reforço:
a regra existia também como `CHECK` no banco, que devolvia o mesmo 422, e o teste só olhava o status. Agora ele
confere a mensagem clara da API e a regra do serviço.

**CI (GitHub Actions, `.github/workflows/ci.yml`).** A cada push e pull request, em máquinas novas e vazias:
1. *Backend*: pytest com cobertura contra um PostgreSQL descartável.
2. *Front*: `npm test` e auditoria das dependências de produção (`npm audit --omit=dev --audit-level=high`).
3. *Ponta a ponta*: PostgreSQL, API e `next dev` de verdade, conferindo a proteção de rotas.

Os avisos moderados que restam no `npm audit` completo estão em ferramentas de desenvolvimento (Jest, ESLint,
`shadcn`) e dependem de atualização das próprias bibliotecas; as correções que o npm sugere são rebaixar versões.

## API
Com o servidor ligado (`uvicorn app.main:app --reload --env-file .env`), a documentação interativa fica em `/docs`.

| Recurso | Rotas |
|---|---|
| Autenticação | `POST /auth/login`, `GET /auth/eu`, `POST /auth/senha` (trocar a própria senha) |
| Usuários (só admin) | `/usuarios` (listar, criar, mudar perfil e ativo), `/usuarios/{id}/senha`, `/usuarios/{id}/auditoria` |
| Clientes | `/clientes` (CRUD, busca por nome, grupo, telefone) |
| Processos | `/processos-obt`, `/processos-ren`, `/processos-pass` (CRUD e filtros) |
| Solicitantes | `/processos/{id}/solicitantes`, `/solicitantes/{id}`, `/solicitantes/{id}/titular` |
| DS-160 | `/solicitantes/{id}/formularios-ds160`, `/formularios-ds160/{id}` |
| Workflow | `POST /processos/{id}/situacao`, `GET /processos/{id}/eventos` |
| Painel | `GET /painel`: uma linha por processo, como a planilha (view `vw_painel_processos`). Total no cabeçalho `X-Total-Count`; período por data com `data` (casv, entrevista, orientacao, despacho, pf, prazo_pf) + `de`/`ate`; no REN, `despacho=pendente` ou `feito`; no OBT, `orientacao=` um dos status |
| Resumo e agenda | `GET /painel/resumo` (contagens por tipo, situação e resultado), `GET /painel/agenda?de=&ate=` (datas do período, até 92 dias; o despacho traz `despachado_em`) |
| Despacho (REN) | `data_despacho` é o prazo, calculado pelo banco (CASV − 7). `despachado_em` é quando foi despachado de verdade (vazio = falta despachar; não aceita data no futuro). A migration 0007 marcou os REN já concluídos do histórico |
| Orientação (OBT) | Na ordem do caminho: Pendente, Opções enviadas (recebeu as opções: Opt A ou padrão), Sem resposta (recebeu e não respondeu), Opt A, Escolheu padrão (sem data ainda), Agendada (exige data) e Fornecidas. Os três novos vieram na migration 0008 ("Sem resposta" se chamava Decidindo até a 0009) |
| Referências | `GET /referencias`: situações por tipo, consulados e demais valores válidos (para filtros e formulários) |

O front (Next.js) fica em [web/](web/README.md). Para ligar a API e o front juntos: `cd web` e `npm run dev`.

Regras: ao criar um processo, o titular (com o nome do cliente), os solicitantes extras e o evento "criado"
são gravados numa transação só. A situação não muda pelo PATCH: só pela rota de workflow, que grava a
mudança e o evento juntos.

### Workflow de situações
- A situação precisa existir para o tipo do processo (ex.: `Pix` só em passaporte).
- Toda mudança gera um evento (situação anterior, nova, motivo, quando).
- Sair de `Concluido` exige motivo e gera o evento `reaberto`; voltar para `Processando` não é bloqueado
  (negativa seguida de nova tentativa é um caso normal).
- A linha do processo é travada durante a mudança (`SELECT ... FOR UPDATE`): duas mudanças simultâneas viram
  uma fila e o histórico nunca registra uma "situação anterior" errada.

## Autenticação
Todas as rotas, menos as de entrada (`/auth/login`, `/auth/google`, `/auth/google/config`) e os health checks,
exigem um token (`Authorization: Bearer <token>`); sem ele, 401.

**Duas formas de entrar:**
- **Google (todos os perfis):** é o caminho normal. O Google só prova quem a pessoa é; **quem pode entrar é o
  nosso cadastro**: o e-mail precisa estar em Usuários e ativo, senão 403 (nada é criado). O perfil vem do
  cadastro, nunca do Google.
- **E-mail e senha (só `admin`):** acesso reserva, para o administrador não ficar trancado fora se o Google ou a
  configuração cair. Os demais perfis não têm senha: a API recusa criar (422) ou redefinir (409) senha de quem não
  é admin, e quem deixa de ser admin perde a senha (fica na auditoria). Quem não é admin e digita a senha certa
  recebe o mesmo 401 de sempre.

```
# 1. crie o primeiro administrador (a senha é pedida no terminal, nunca vai para o código ou o histórico)
python -m scripts.usuario criar --nome "Seu Nome" --email voce@empresa.com.br --perfil admin
# 2. usuários vindos da importação não têm senha; defina a de cada um
python -m scripts.usuario senha --email fulano@empresa.com.br
# 3. na API: POST /auth/login com {"email", "senha"} devolve o token; no /docs, botão "Authorize" e cole o token
```

- A senha vira hash argon2 (com sal) e nunca é guardada. Mínimo de 10 caracteres.
- O token (JWT) dura 30 minutos (`JWT_EXPIRA_MINUTOS`) e leva só o id do usuário. **Perfil e `ativo` são lidos
  do banco a cada requisição**: desativar alguém (`ativo = false`) ou mudar seu perfil vale na hora.
- Sessão deslizante: `POST /auth/renovar` troca um token ainda válido por um novo com a validade cheia (o front
  chama enquanto a pessoa usa o sistema). O token guarda a hora do login e a renovação nunca passa de
  `JWT_SESSAO_MAXIMA_HORAS` (padrão 10) depois dele: aí responde 401 e é preciso entrar de novo.
- Falhas de login por senha (senha errada, e-mail inexistente, usuário inativo, sem senha ou que não é admin) dão a
  mesma resposta 401. Quem não vai poder entrar nem chega a ter a senha conferida.
- `JWT_SECRET` (mínimo 32 caracteres) vem do `.env`; sem ele a API recusa emitir tokens.
- Processos e eventos registram quem os criou ou alterou.

### Login com o Google (OpenID Connect, código de autorização + PKCE)
1. O front (`web/app/api/auth/google`) guarda `state`, `nonce` e o verificador PKCE num cookie httpOnly de 10
   minutos e manda a pessoa ao Google (`openid email profile`, `prompt=select_account`).
2. O Google devolve a pessoa a `/api/auth/google/callback` com um `code`. O front confere o `state` e entrega
   `code`, verificador, `nonce` e `redirect_uri` à API (`POST /auth/google`).
3. A **API** troca o código pelo `id_token` (a chave secreta só existe aqui) e confere **assinatura** (chaves
   públicas do Google, RS256 fixo), **emissor**, **destinatário** (`aud` = nosso ID de cliente), **validade**,
   **`nonce`** e **`email_verified`**. Só então procura o e-mail no cadastro (sem diferenciar maiúsculas) e, se
   estiver ativo, devolve o nosso token. A sessão (cookie, renovação, teto de 10 h) é a mesma do login por senha.

| Variável (`.env` da raiz, só a API lê) | Para quê |
| --- | --- |
| `GOOGLE_CLIENT_ID` | ID do cliente OAuth (Google Cloud Console → Clientes). Não é segredo. |
| `GOOGLE_CLIENT_SECRET` | Chave secreta do cliente. **Segredo**: só no `.env`, nunca em chat, commit ou log. |
| `GOOGLE_ALLOWED_DOMAIN` | Opcional: aceita só e-mails desse domínio (ex.: `concept.com.br`). Vazio = qualquer. |

- **Endereço de retorno:** o Google só devolve a pessoa a endereços cadastrados, **idênticos** (letra por letra) em
  Google Cloud → Clientes → "URIs de redirecionamento autorizados". Cadastre um por ambiente:
  `http://localhost:3000/api/auth/google/callback` (use `localhost`, não `127.0.0.1`),
  `https://SEU-DOMINIO.ngrok-free.dev/api/auth/google/callback` e, na VPS,
  `https://seu.dominio.com.br/api/auth/google/callback`. Outro endereço dá `redirect_uri_mismatch`.
- O front descobre o próprio endereço pelo `X-Forwarded-Host/Proto` (ngrok, nginx) ou pelo `Host`. Para fixar,
  defina `APP_URL` no ambiente do front (ex.: `APP_URL=https://vistos.concept.com.br`).
- Erros voltam ao login com um motivo (`/login?erro=google_sem_acesso`, `google_cancelado`, `google_expirou`...) que a
  tela traduz. Nada do Google (nem o código) fica na URL. Falhas e logins vão para o log `concept.acesso` com o
  e-mail mascarado, e o limite de tentativas por IP vale também aqui.
- Sem `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`, `/auth/google/config` responde 503 e a tela avisa que o login
  com o Google não está disponível (o admin continua entrando com a senha).

## Proteções contra abuso
Valem igual no ngrok e numa VPS (estão no código, não no caminho até ele). Os números vêm do `.env`.

| Proteção | Padrão | Variável |
| --- | --- | --- |
| Tentativas de login por IP (certas ou erradas) | 10 por minuto | `LIMITE_LOGIN_POR_MINUTO` |
| Senhas erradas por conta: depois disso a conta trava, mesmo com a senha certa | 5 em 15 minutos | `LIMITE_FALHAS_DE_SENHA` |
| Senha atual errada na troca de senha (mesma regra, por usuário) | 5 em 15 minutos | `LIMITE_FALHAS_DE_SENHA` |
| Requisições por IP, em qualquer rota (um escritório inteiro pode ter um IP só) | 600 por minuto | `LIMITE_REQUISICOES_POR_MINUTO` |
| Tamanho do corpo da requisição | 1024 KB | `LIMITE_CORPO_KB` |
| Tempo máximo de uma consulta no Postgres (`statement_timeout`) | 15 s | `DB_TEMPO_MAXIMO_CONSULTA_MS` |
| Conexões com o banco (pool + extras) e espera por uma livre | 5 + 5, 10 s | `DB_POOL`, `DB_POOL_EXTRA`, `DB_ESPERA_CONEXAO` |
| Itens por página nas listagens | 200 | (fixo nas rotas) |

- Passou do limite: **429** com `Retry-After` e "Muitas tentativas. Tente de novo em N minutos". Corpo grande: 413.
  Consulta cortada: 503 "A consulta demorou demais". Pool esgotado: 503 "Servidor ocupado".
- **IP de quem acessa:** quem chama a API é o servidor do Next, então o IP da conexão é sempre 127.0.0.1. O Next
  repassa o IP real no cabeçalho `X-Cliente-IP` (o último do `X-Forwarded-For`, que é o que o ngrok/nginx viu) e
  a API só acredita nele quando a conexão vem de um endereço de `API_PROXIES_CONFIAVEIS` (padrão `127.0.0.1,::1`).
  Por isso a API deve escutar só em `127.0.0.1` (o padrão do uvicorn): exposta direto, o limite continua valendo
  pelo IP da conexão, mas o certo é só o Next falar com ela.
- Falhas e bloqueios de login vão para o log (`concept.acesso`) com o IP e o e-mail mascarado (`a***@dominio.com`).
- **Logs:** cada requisição ganha um código (cabeçalho `X-Request-ID`, também aceito de fora se for simples) e
  uma linha no log com método, caminho, status, duração, id do usuário e IP. Nunca entram senha, token, corpo nem
  parâmetros da URL. Erro não tratado vira 500 com o código (o traceback fica só no log); o front mostra o
  código nos erros 5xx, para a pessoa informar ao suporte. `LOG_NIVEL` e `LOG_FORMATO` (`texto` ou `json`).
- **Idempotência:** as criações (POST de clientes, processos, pessoas, DS-160, usuários e a mudança de situação)
  aceitam o cabeçalho `Idempotency-Key`. O mesmo código reenviado (duplo clique, F5, rede que repete) devolve a
  resposta da primeira vez (cabeçalho `Idempotent-Replayed: true`) e não cria nada de novo; reenvio enquanto o
  primeiro ainda roda espera o resultado. Só o sucesso fica guardado (24 h, tabela `chaves_idempotencia`): erro
  libera a chave para corrigir e tentar de novo. Mesmo código com dados ou rota diferentes: 422. Login e troca de
  senha ficam de fora (resposta com token). O front gera uma chave por formulário (`useChaveDeIdempotencia`)
  nos cadastros de cliente, processo e usuário. Limite honesto: a resposta é guardada depois da gravação; se o
  servidor cair nesse instante, a reserva expira em 1 minuto e o reenvio executa de novo.
- **Saúde:** `GET /saude` (a API está de pé? não toca no banco) e `GET /pronto` (o banco responde? 503 se não).
  Públicas, devolvem só `{"status": ...}`, não contam no limite por IP e ficam fora do log normal (só em `DEBUG`).
  Separadas de propósito: se o banco cai, a API não deve ser reiniciada à toa (é o que um `healthcheck` do Docker
  e o Nginx vão usar no Projeto 5: `/saude` para reiniciar, `/pronto` para tirar da rotação).
- `API_DOCS=false` tira o `/docs` e o `/openapi.json` (use em produção).
- A contagem fica na memória da API: vale para **um processo** (o nosso caso). Com vários workers ou servidores,
  cada um contaria por si; aí a contagem precisa ir para o Redis. Reiniciar a API zera as contagens.
- O front manda cabeçalhos de segurança em toda página (`web/next.config.ts`): sem iframe de outro site
  (`X-Frame-Options`, `frame-ancestors`), `nosniff`, `Referrer-Policy`, HSTS e `Permissions-Policy`.

## Autorização por perfil
O perfil define o que cada pessoa pode fazer, escolhido pelo método HTTP numa regra única (`app/main.py`),
então uma rota nova já nasce protegida (há um teste que percorre todas as rotas para garantir isso).

| Perfil | Pode |
|---|---|
| `leitor` | consultar (GET) |
| `atendente` | consultar, criar e editar (POST, PATCH), incluindo mudar a situação de um processo |
| `admin` | tudo: apagar (DELETE) e administrar usuários |

- **401** = não está logado (sem token ou token inválido). **403** = está logado, mas o perfil não permite.
- Perfil desconhecido não pode nada (nega por padrão).
- Mudanças de perfil, `ativo`, nome e senha de um usuário ficam registradas (quem fez, o que mudou, quando),
  sem nunca guardar a senha.
- A empresa nunca fica sem um administrador ativo: a API recusa (409) rebaixar ou desativar o último.
- Excluir cliente (`DELETE /clientes/{id}`, só admin): com processos, a API recusa (409) a menos que venha
  `com_processos=true`; aí apaga junto processos, solicitantes, formulários e eventos. É definitivo.
- Só `admin` tem senha; os outros perfis entram com o Google, pelo e-mail cadastrado (veja "Autenticação").
- **Auditoria de clientes e processos** (só admin vê): toda mudança em clientes, processos (e os detalhes de
  cada tipo), pessoas e DS-160 fica registrada **pelo próprio PostgreSQL** (trigger, migration 0011), com
  antes e depois (na edição, só os campos que mudaram), quem fez, o código da requisição (o mesmo do log) e a
  origem (`api`, `seed`, `importacao` ou `banco` para edição direta no psql, sem usuário). Pega também a
  cascata do DELETE e UPDATEs em massa. A API conta ao banco quem é o usuário no começo de cada transação
  (`set_config(..., true)`, que não vaza para a próxima requisição da mesma conexão).
  - O rastro sobrevive à remoção (sem FK): `GET /auditoria?cliente_id=` funciona com o cliente já apagado,
    e `?tabela=clientes&acao=apagou` lista os removidos com os dados que tinham.
  - A tabela só aceita INSERT: UPDATE e DELETE nela dão erro. (Um superusuário do banco ainda pode desligar o
    trigger: isso protege contra a aplicação e contra engano, não contra o dono do servidor.)
  - Nada é apagado por prazo: clientes antigos voltam e o histórico é útil. Os dados pessoais ficam
    guardados; por isso só admin lê.
  - Na tela: "Histórico de alterações" nas páginas de cliente e de processo, só para admin.

## Importação do banco do Projeto 1
`app/importacao/projeto1.py` migra clientes e processos do Concept Client Registry para este esquema
(o código não contém dados; as URLs vêm do `.env` de cada máquina).

```
# .env: SOURCE_DATABASE_URL (banco antigo, só leitura) e DATABASE_URL (banco novo, vazio, após alembic upgrade head)
python -m scripts.importar_projeto1 --simular                       # ensaio: faz tudo e desfaz no final
python -m scripts.importar_projeto1 --usuarios usuarios.csv         # grava de verdade
```

- Roda numa transação só e imprime a conferência origem x destino (clientes, processos, solicitantes, formulários).
  Se clientes ou processos não baterem, nada é gravado.
- `n_solicitantes` vira N solicitantes (o titular leva o nome do cliente; os outros ganham o primeiro nome que
  aparece nos códigos do DS-160). Os códigos viram formulários, `notas_ds160` vira a observação do processo e
  o consulado `N/D` vira consulado vazio. Esses processos (data marcada e consulado vazio) continuam legíveis e
  editáveis: a regra "com data de CASV ou entrevista, informe o consulado" vale ao criar e, no PATCH, só quando a
  edição mexe no consulado ou nessas datas.
- **Padronização na importação** (o banco antigo não é alterado): o leitor de códigos tolera traço opcional, "novo" sem
  traço, vários códigos por linha e comentários; e-mail em minúsculas, telefone só dígitos, nomes em CAIXA ALTA em
  Nome Próprio e grupos unificados.
- `n_solicitantes` é a verdade: o processo tem exatamente N solicitantes. Código repetido (cliente que passou de REN
  para OBT) fica no processo mais recente; o outro guarda uma nota na observação. Passaporte sem situação vira `Pendente`.
- A conferência exige que clientes, processos, solicitantes e formulários batam (formulário = criado ou repetido
  explicado). Tudo o que foi decidido por regra vai para `excecoes_importacao.csv` (fora do Git), sempre com as
  mesmas colunas: `categoria;tabela;id_origem;cliente_id_origem;detalhe;acao`.
- `--usuarios` é opcional: CSV local (`nome;email;perfil`, fora do Git) dos funcionários que viram usuários.
- Recusa um banco de destino que já tenha dados e funciona com bancos antigos sem as colunas do DS-160.

## Dados fictícios (seed)
Para a máquina de testes e demonstrações. Tudo é inventado (nomes sorteados, e-mails `@exemplo.com`, códigos
DS-160 aleatórios) e a semente é fixa: o mesmo comando gera sempre o mesmo conjunto.

```
python -m scripts.seed_ficticio --confirmo-dados-ficticios     # pede a senha dos usuários demo no terminal
```

- Cria 3 usuários demo (`admin@`, `atendente@` e `leitor@exemplo.com`) e um ex-funcionário inativo, 36 clientes e
  seus processos dos três tipos, com solicitantes, formulários DS-160 e histórico gerado pelo mesmo serviço da API.
- Inclui cenários prontos para demonstrar: negativa seguida de nova tentativa e processo reaberto com motivo.
- **Recusa rodar em banco que já tenha clientes** e exige `--confirmo-dados-ficticios`, para nunca se misturar
  com os dados reais da outra máquina.

## Estado
Etapas 1 a 8 concluídas (MVP): modelagem, SQLAlchemy + Alembic, CRUD com painel, workflow com histórico,
importação do Projeto 1, autenticação por senha + JWT, autorização por perfil com administração de usuários,
testes com CI e seed fictício, e o "Entrar com o Google" (etapa 5b). O front (`web/`) está em andamento.
