# Concept Vistos — front

Interface web do **Concept Visa Workflow**: o time da Concept Vistos acompanha aqui os processos de visto
(obtenção, renovação) e passaporte. Todo dado vem da API Python da pasta acima; o front não tem banco próprio.

## Funcionalidades (fase atual)

- Login com o e-mail e a senha da API. O token fica num cookie `httpOnly`: o navegador nunca o lê.
- Rotas protegidas: sem sessão, a pessoa vai ao login e volta para onde ia depois de entrar.
- Menu por perfil (leitor, atendente, admin). Esconder um botão não protege nada: quem decide é a API (401/403).
- Início com um "cartão de embarque" por tipo de processo (em andamento e situações abertas).
- Identidade Concept Vistos: logo em vetor, azul `#1d9d9d`, tinta `#050510`, papel `#f5f5f5`, tema claro e
  escuro, animações decorativas (avião, pins, carimbo) que respeitam "reduzir movimento".

Próximas fases: processos (tabela, kanban e detalhe em "passaporte"), agenda, clientes, novo processo e usuários.

## Como rodar

Pré-requisitos: Node.js 20.9+ e a API rodando (veja o README da raiz: `uvicorn app.main:app --env-file .env`).

```powershell
cd web
npm install
copy .env.example .env.development   # preencha API_URL
npm run dev                           # http://localhost:3000
```

## Testes

```powershell
npm test           # Prettier + ESLint + TypeScript + Jest (unitários e de componentes)
npm run test:e2e   # sobe o next dev e testa a porta de entrada de verdade
```

## Variáveis de ambiente

| Variável  | Para quê                                                                          |
| --------- | --------------------------------------------------------------------------------- |
| `API_URL` | Endereço da API Python (ex.: `http://127.0.0.1:8000`). Só o servidor do Next usa. |

## Estrutura

| Pasta         | O que tem                                                                                           |
| ------------- | --------------------------------------------------------------------------------------------------- |
| `app/`        | Páginas (App Router). `(app)/` é a área logada; `login/` é pública; `acoes/` são Server Actions.    |
| `components/` | `marca/` (logo), `login/` (cena do voo), `shell/` (menu), `movimento/` (animações), `ui/` (shadcn). |
| `lib/`        | `api.ts` (única porta para a API), `sessao.ts`, `permissoes.ts`, `erros.ts`, `formatos.ts`.         |
| `proxy.ts`    | Checagem otimista de sessão (o antigo `middleware` do Next 16).                                     |
| `tests/`      | Jest: `lib/`, `componentes/` e `e2e/`.                                                              |

Commits seguem Conventional Commits (`npm run commit`).
