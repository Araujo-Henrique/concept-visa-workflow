# Concept Vistos — front

Interface web do **Concept Visa Workflow**: o time da Concept Vistos acompanha aqui os processos de visto
(obtenção, renovação) e passaporte. Todo dado vem da API Python da pasta acima; o front não tem banco próprio.

## Funcionalidades (fase atual)

- Login com o e-mail e a senha da API. O token fica num cookie `httpOnly`: o navegador nunca o lê.
- Rotas protegidas: sem sessão, a pessoa vai ao login e volta para onde ia depois de entrar.
- Menu por perfil (leitor, atendente, admin). Esconder um botão não protege nada: quem decide é a API (401/403).
- Início com um "cartão de embarque" por tipo de processo (em andamento e situações abertas).
- **Processos**: abas OBT/REN/PASS, filtros na URL (busca, situação, consulado, resultado, período de uma data),
  tabela paginada e **quadro** (kanban): arrastar um card muda a situação de verdade (mouse ou teclado), com
  atualização otimista; reabrir um concluído pede o motivo.
- **Detalhe em passaporte**: capa, página de dados, pessoas com DS-160 (resultado editável) e carimbos do
  histórico; a rota de situações ao lado "carimba" a mudança.
- **Busca global** (Ctrl+K): número do processo ou nome do cliente.
- Identidade Concept Vistos: logo em vetor, azul `#1d9d9d`, tinta `#050510`, papel `#f5f5f5`, tema claro e
  escuro, animações decorativas (avião, pins, carimbo) que respeitam "reduzir movimento".

Próximas fases: agenda, clientes, novo processo (e edição dos dados) e usuários.

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
