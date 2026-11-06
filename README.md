# Concept Visa Workflow

Sistema de acompanhamento do fluxo de processos de visto (obtenção, renovação e passaporte), com histórico
de situações, usuários e perfis. Projeto 2 trilha de estudos; veja [docs/PLANO.md](docs/PLANO.md) para a
modelagem (DER) e as regras.

> Todos os dados de exemplo deste repositório são fictícios.

## Stack
Python 3.14, SQLAlchemy 2.0 (ORM), Alembic (migrations), PostgreSQL, FastAPI, pytest.

## Mesma base de código, duas máquinas
Só o `.env` e o banco mudam; nada específico de máquina fica no código.

| | Máquina de testes | Máquina real |
|---|---|---|
| Banco | `concept_visa_workflow` (+ `_test`) | `concept_visa_workflow` |
| Dados | seed fictício (etapa 8) | importados localmente, fora do repositório |
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
esquema pelas migrations.
```
pytest
```

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
| Painel | `GET /painel`: uma linha por processo, como a planilha (view `vw_painel_processos`). Total no cabeçalho `X-Total-Count`; período por data com `data` (casv, entrevista, orientacao, despacho, pf, prazo_pf) + `de`/`ate` |
| Resumo e agenda | `GET /painel/resumo` (contagens por tipo, situação e resultado), `GET /painel/agenda?de=&ate=` (datas do período, até 92 dias) |
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
Todas as rotas, menos o login, exigem um token (`Authorization: Bearer <token>`); sem ele, 401.

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
- Falhas de login (senha errada, e-mail inexistente, usuário inativo ou só-Google) dão a mesma resposta 401.
  Usuário inativo nem chega a ter a senha conferida.
- `JWT_SECRET` (mínimo 32 caracteres) vem do `.env`; sem ele a API recusa emitir tokens.
- Processos e eventos registram quem os criou ou alterou.

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
- "Entrar com Google" fica como melhoria futura: será uma segunda forma de entrar, ligada ao mesmo usuário
  pelo e-mail, sem alterar o que existe.

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
  o consulado `N/D` vira consulado vazio.
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

## Estado
Etapas 1 a 6 concluídas (MVP): modelagem, SQLAlchemy + Alembic, CRUD com painel, workflow com histórico,
importação do Projeto 1, autenticação por senha + JWT e autorização por perfil com administração de usuários.
Próximas: testes em CI e seed fictício (etapas 7 e 8); "Entrar com Google" como melhoria posterior.
