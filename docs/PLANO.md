# Concept Visa Workflow — Plano e modelagem

> Todos os dados deste repositório são fictícios.

## Objetivo
Sistema interno para acompanhar o fluxo dos processos de visto (obtenção, renovação, passaporte), com
histórico de mudanças de situação, usuários, perfis de acesso e login. O diagrama das tabelas está em
[DER.md](DER.md).

## Etapas

| # | Etapa | Estado |
|---|---|---|
| 1 | Modelagem (este documento e o DER) | concluída |
| 2 | SQLAlchemy 2.0 + Alembic (modelos e migration base) | concluída |
| 3 | CRUD com ORM, schemas Pydantic, view e rota do painel | concluída |
| 4 | Workflow: eventos, motivo ao reabrir, trava de linha (`FOR UPDATE`) | concluída |
| 5a | Autenticação por senha + JWT | concluída |
| 5b | "Entrar com Google" (OpenID Connect) | adiada: melhoria depois do MVP |
| 6 | Autorização por perfil (401 x 403), administração de usuários e auditoria | concluída |
| 7 | Testes e CI (GitHub Actions: backend, front e ponta a ponta), cobertura e mutações | concluída |
| 8 | Seed fictício, README e DER no repositório | concluída |
| — | Importação do Projeto 1 (clientes e processos reais, na máquina real) | concluída |
| — | Front-end (Next.js, pasta `web/`) | em andamento |

Fora deste projeto: Docker/VPS/Nginx/HTTPS e limite de tentativas de login (Projeto 5), webhooks e
integrações (Projeto 3), acesso do cliente ao próprio processo (Projeto 5).

## Tabelas

| Tabela | Colunas principais | Observações |
|---|---|---|
| `perfis` | id, nome | admin, atendente, leitor |
| `usuarios` | id, nome, email, senha_hash, perfil_id, ativo | e-mail único (minúsculo); `senha_hash` nulo = só Google |
| `auditoria_usuarios` | id, usuario_id, feito_por_id, campo, valor_anterior, valor_novo, criado_em | quem mudou perfil, ativo, nome ou senha de quem; nunca guarda a senha |
| `clientes` | id, nome, email, telefone, grupo | nome único (sem diferenciar maiúsculas) |
| `situacoes` | tipo, nome | PK (tipo, nome); situações válidas por tipo de processo |
| `processos` | id, tipo, cliente_id, situacao, processo_anterior_id, observacao, criado_por_id, criado_em, atualizado_em | tipo OBT/REN/PASS; único (id, tipo); FK (tipo, situacao) → situacoes; auto-FK `processo_anterior_id` (nova tentativa) |
| `processo_obt` | processo_id, tipo, consulado, monitoramento, data_casv, data_entrevista, data_vencimento_taxa, status_rascunho, orientação (+data, +usuário), código de rastreio | 1:1 com processos; consulado opcional |
| `processo_ren` | processo_id, tipo, consulado, data_casv, data_despacho (gerada = CASV − 7), docs, status_rascunho, endereço, rastreio | 1:1 com processos |
| `processo_pass` | processo_id, tipo, data_pf, prazo_pf | 1:1 com processos |
| `solicitantes` | id, processo_id, nome, titular, resultado | exatamente um titular por processo (índice único parcial); resultado por pessoa |
| `formularios_ds160` | id, solicitante_id, codigo, status, observacao | código único, formato `AA00` + 6 alfanuméricos; uma pessoa pode ter vários |
| `eventos` | id, processo_id, usuario_id, tipo, situacao_anterior, situacao_nova, motivo, criado_em | motivo obrigatório quando o tipo é `reaberto` |
| `vw_painel_processos` (view) | uma linha por processo, no formato da planilha | alimenta `GET /painel`; criada na migration 0003 e ampliada na 0005 |

Herança de tabela unida (joined table): `processos` guarda o que é comum e cada `processo_*` o que é
específico; a FK composta `(processo_id, tipo)` impede, por exemplo, um detalhe de REN ligado a um processo OBT.

Relações 1:N: a tabela do lado "muitos" guarda o id do lado "um" (`solicitantes.processo_id`,
`formularios_ds160.solicitante_id`). A quantidade de solicitantes é contada (`count`), não armazenada.

## Regras de negócio
- Um cliente pode ter vários processos. Nova tentativa após negativa = novo processo para o mesmo
  cliente, ligado ao anterior por `processo_anterior_id`.
- Não há bloqueio de Concluído → Processando.
- Toda mudança de situação gera um evento. Sair de Concluído exige um motivo curto (regra no serviço e, como
  rede de segurança, `CHECK` no banco).
- **Consulado:** pode ficar vazio enquanto não há data marcada. "Com data de CASV, o consulado é obrigatório"
  vale na API para OBT e REN; na REN o banco também a impõe (`CHECK`). No OBT o banco não impõe, porque o
  histórico importado tem processos com data marcada e consulado desconhecido (antigo `N/D`).
- Regras por situação continuam (ex.: orientação `Agendada` exige data).
- "Pelo menos um titular" é garantido pelo serviço, na mesma transação que cria o processo (e testado);
  "no máximo um" é garantido pelo banco.
- Cadastros são feitos em nome de solicitantes; o titular copia o nome do cliente na criação.
- Os funcionários do sistema antigo entram como usuários só se constarem no `usuarios.csv` local; os demais
  ficam apenas como nome nos registros de orientação.
- A empresa nunca fica sem um administrador ativo (a API recusa rebaixar ou desativar o último).

## Autenticação e autorização
- Senha com hash argon2 + JWT (5a). O token leva só o id e a validade; perfil e `ativo` são lidos do banco a
  cada requisição, então desativar alguém ou mudar seu perfil vale na hora.
- Perfis: `leitor` consulta, `atendente` consulta, cria e edita, `admin` também apaga e administra usuários.
  A permissão é escolhida pelo método HTTP numa regra única, aplicada a todos os routers.
- Google OpenID Connect (5b, adiada): será uma segunda forma de entrar, ligada ao mesmo usuário pelo e-mail.
  O token é verificado com a biblioteca do Google; domínio do Workspace e Client ID virão de variáveis de
  ambiente. O usuário precisa existir e estar ativo em `usuarios`, senão 403.

## Qualidade
- **Backend:** pytest contra um PostgreSQL de verdade (`TEST_DATABASE_URL`, banco `_test` recriado pelas
  migrations), com cobertura de linhas e ramos medida no CI.
- **Mutações:** regras críticas (autorização, trava do último admin, workflow, login, `FOR UPDATE`) foram
  quebradas de propósito para conferir que algum teste falha. Duas sobreviveram, porque o banco também
  recusava e o teste só olhava o status; os testes passaram a conferir a mensagem e o serviço.
- **Front:** Prettier, ESLint, TypeScript e Jest; mais um teste ponta a ponta da proteção de rotas.
- **CI (GitHub Actions):** três jobs em paralelo (backend com PostgreSQL, front, ponta a ponta com Next + API +
  PostgreSQL) e auditoria de dependências de produção.
