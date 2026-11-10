# Concept Vistos — front

Interface web do **Concept Visa Workflow**: o time da Concept Vistos acompanha aqui os processos de visto
(obtenção, renovação) e passaporte. Todo dado vem da API Python da pasta acima; o front não tem banco próprio.

## Funcionalidades (fase atual)

- Login com o **Google** (todos os perfis; só entra quem tem o e-mail cadastrado em Usuários e ativo) ou, como
  reserva do administrador, com e-mail e senha (o acesso por senha fica recolhido na tela). O token fica num
  cookie `httpOnly`: o navegador nunca o lê. O fluxo está em `app/api/auth/google` e `lib/google-oauth.ts`.
- Rotas protegidas: sem sessão, a pessoa vai ao login e volta para onde ia depois de entrar.
- Sessão deslizante: enquanto a pessoa usa o sistema, o token é renovado (no máximo a cada 5 minutos, via
  `POST /auth/renovar`). Parada, aparece um aviso 2 minutos antes de vencer ("Continuar conectado"); vencida,
  volta ao login com "Sua sessão expirou". Cada login vale no máximo `JWT_SESSAO_MAXIMA_HORAS` (API).
  O cookie `cv_expira` (sem o token, legível pelo navegador) diz quando a sessão vence.
- Proteções: a API limita tentativas de login (por IP e por conta) e requisições por IP; o front repassa o IP de
  quem acessa (`lib/ip-cliente.ts`, cabeçalho `X-Cliente-IP`) e mostra o tempo de espera quando a API responde 429.
  Toda página sai com cabeçalhos de segurança (`next.config.ts`). Detalhes no README da raiz.
- Menu por perfil (leitor, atendente, admin). Esconder um botão não protege nada: quem decide é a API (401/403).
- Início com um "cartão de embarque" por tipo de processo (em andamento e situações abertas) e o **painel de
  embarque**: as datas marcadas dos próximos 7 dias, no estilo do letreiro de partidas do aeroporto.
- **Agenda**: calendário do mês com orientações, CASV, entrevistas, despachos e PF; filtro por tipo de
  compromisso, setas do teclado para andar pelos dias e o painel do dia com o link de cada processo.
- **Processos**: abas OBT/REN/PASS, filtros na URL (busca, situação, consulado, resultado, período de uma data),
  tabela paginada e **quadro** (kanban): arrastar um card muda a situação de verdade (mouse ou teclado), com
  atualização otimista; reabrir um concluído pede o motivo.
- **Detalhe em passaporte**: capa, página de dados (com o e-mail do cliente, que serve de login no consulado), pessoas com DS-160 (resultado editável) e carimbos do
  histórico; a rota de situações ao lado "carimba" a mudança.
- **Busca global** (Ctrl+K): número do processo ou nome do cliente.
- **Clientes**: lista em ordem alfabética com busca única (nome, e-mail ou telefone), cadastro e edição, e a
  ficha do cliente com os processos dele ("histórico de viagens"), telefone formatado e link do WhatsApp.
  Admin pode excluir o cliente junto com os processos (confirma digitando o nome; não dá para desfazer).
- **Novo processo**: assistente em cinco passos (cliente, tipo, dados, pessoas, embarque); dá para cadastrar o
  cliente no meio do caminho. Avisa as regras (consulado com data, orientação agendada com data) antes de enviar.
- **Editar o processo** no passaporte: dados (só o que mudou vai para a API), pessoas (incluir, trocar o titular,
  resultado) e códigos DS-160 (incluir e mudar o status). Remover pessoa ou código é só do admin.
- Identidade Concept Vistos: logo em vetor, azul `#1d9d9d`, tinta `#050510`, papel `#f5f5f5`, tema claro e
  escuro, animações decorativas (avião, pins, carimbo) que respeitam "reduzir movimento".

- **Usuários** (só admin): a equipe como crachás de tripulação; criar (só o administrador tem senha, com gerador
  e copiar; os outros perfis entram com o Google e não pedem senha), editar nome e perfil, redefinir senha (só de
  administrador), desativar ou reativar o acesso (ninguém se desativa e a API sempre mantém um admin ativo) e o
  histórico de cada usuário (a senha nunca aparece).
- **Minha conta** (todos): o próprio crachá; o administrador também troca a senha (pede a atual).

## Como rodar

Pré-requisitos: Node.js 20.9+ e a API configurada (venv e `.env` da raiz; veja o README da raiz).

```powershell
cd web
npm install
copy .env.example .env.development   # preencha API_URL
npm run dev                           # sobe a API (porta 8000) e o front (http://localhost:3000) juntos
```

`npm run dev` liga os dois servidores num terminal só (logs marcados `[api]` e `[web]`); `Ctrl+C` desliga
os dois. Para subir só o front (com a API já ligada em outro terminal): `npx next dev`.

### Mostrar para alguém de fora (ngrok)

```powershell
copy .env.example .env.production.local   # API_URL para o modo produção (fica fora do Git)
npm run publicar                          # build + API + front de produção em http://localhost:3000
ngrok http 3000                           # em outro terminal: o link público é a linha "Forwarding"
```

**Login com o Google no ngrok:** cadastre `https://SEU-DOMINIO.ngrok-free.dev/api/auth/google/callback` em Google
Cloud → Clientes → "URIs de redirecionamento autorizados" (o domínio é o da linha "Forwarding"; é fixo no plano
gratuito). Abra o site pelo link do ngrok (ou por `http://localhost:3000`, nunca `127.0.0.1`).

`Ctrl+C` no ngrok derruba o link; no `publicar`, desliga a API e o front. Rode de novo o `publicar` depois de
cada alteração (ele refaz a build). Não use `npm run dev` para mostrar: é mais lento e expõe detalhes de erro.

## Testes

```powershell
npm test           # Prettier + ESLint + TypeScript + Jest (unitários e de componentes)
npm run test:e2e   # sobe o next dev e testa a porta de entrada de verdade
```

## Variáveis de ambiente

| Variável  | Para quê                                                                                                               |
| --------- | ---------------------------------------------------------------------------------------------------------------------- |
| `API_URL` | Endereço da API Python (ex.: `http://127.0.0.1:8000`). Só o servidor do Next usa.                                      |
| `APP_URL` | Opcional: endereço público do site (ex.: `https://vistos.concept.com.br`). Sem ele, vale o que o ngrok/nginx informam. |

## Estrutura

| Pasta         | O que tem                                                                                           |
| ------------- | --------------------------------------------------------------------------------------------------- |
| `app/`        | Páginas (App Router). `(app)/` é a área logada; `login/` é pública; `acoes/` são Server Actions.    |
| `components/` | `marca/` (logo), `login/` (cena do voo), `shell/` (menu), `movimento/` (animações), `ui/` (shadcn). |
| `lib/`        | `api.ts` (única porta para a API), `sessao.ts`, `permissoes.ts`, `erros.ts`, `formatos.ts`.         |
| `proxy.ts`    | Checagem otimista de sessão (o antigo `middleware` do Next 16). Server Actions passam direto.       |
| `tests/`      | Jest: `lib/`, `componentes/` e `e2e/`.                                                              |

Commits seguem Conventional Commits (`npm run commit`).
