# Concept Visa Workflow — Plano e modelagem

> Todos os dados deste repositório são fictícios.

## Objetivo
Sistema interno para acompanhar o fluxo dos processos de visto (obtenção, renovação, passaporte), com
histórico de mudanças de situação, usuários, perfis de acesso e login (senha e Google Workspace).

## Etapas
1. Modelagem (este documento)
2. SQLAlchemy 2.0 + Alembic (modelos e migration base)
3. CRUD com ORM, reaproveitando schemas Pydantic e testes
4. Workflow: eventos, motivo ao reabrir, regras por situação
5. Autenticação: 5a senha + JWT; 5b "Entrar com Google" (OpenID Connect)
6. Autorização por perfil (401 x 403)
7. Testes e CI (GitHub Actions)
8. Seed fictício, README e DER no repositório

Fora deste projeto: Docker/VPS/Nginx/HTTPS (Projeto 5), webhooks e integrações (Projeto 3),
acesso do cliente ao próprio processo (Projeto 5). Front-end começa depois da etapa 6.

## Tabelas (DER)

| Tabela | Colunas principais | Observações |
|---|---|---|
| `perfis` | id, nome | admin, atendente, leitor |
| `usuarios` | id, nome, email, senha_hash, perfil_id, ativo | e-mail único (minúsculo); `senha_hash` nulo = só Google |
| `clientes` | id, nome, email, telefone, grupo | nome único (sem diferenciar maiúsculas) |
| `situacoes` | tipo, nome | PK (tipo, nome); situações válidas por tipo de processo |
| `processos` | id, tipo, cliente_id, situacao, processo_anterior_id, criado_por_id, criado_em, atualizado_em | tipo OBT/REN/PASS; único (id, tipo); FK (tipo, situacao) → situacoes; auto-FK `processo_anterior_id` (nova tentativa) |
| `processo_obt` | processo_id, tipo, consulado, monitoramento, datas, status_rascunho, orientação (+data, +usuário), rastreio | 1:1 com processos |
| `processo_ren` | processo_id, tipo, consulado, data_casv, data_despacho (gerada = CASV − 7), docs, endereço, rastreio | 1:1 com processos |
| `processo_pass` | processo_id, tipo, data_pf, prazo_pf | 1:1 com processos |
| `solicitantes` | id, processo_id, nome, titular, resultado | exatamente um titular por processo (índice único parcial); resultado por pessoa |
| `formularios_ds160` | id, solicitante_id, codigo, status, observacao | código único, formato `AA00` + 6 alfanuméricos; uma pessoa pode ter vários |
| `eventos` | id, processo_id, usuario_id, tipo, situacao_anterior, situacao_nova, motivo, criado_em | motivo obrigatório quando o tipo é `reaberto` |

Herança de tabela unida (joined table): `processos` guarda o que é comum e cada `processo_*` o que é
específico; a FK composta `(processo_id, tipo)` impede, por exemplo, um detalhe de REN ligado a um processo OBT.

Relações 1:N: a tabela do lado "muitos" guarda o id do lado "um" (`solicitantes.processo_id`,
`formularios_ds160.solicitante_id`). A quantidade de solicitantes é contada (`count`), não armazenada.

## Regras de negócio
- Um cliente pode ter vários processos. Nova tentativa após negativa = novo processo para o mesmo
  cliente, ligado ao anterior por `processo_anterior_id`.
- Não há bloqueio de Concluído → Processando.
- Toda mudança de situação gera um evento. Sair de Concluído exige um motivo curto.
- Regras por situação continuam (ex.: Agendada exige data).
- "Pelo menos um titular" é garantido pelo serviço, na mesma transação que cria o processo (e testado);
  "no máximo um" é garantido pelo banco.
- Cadastros são feitos em nome de solicitantes; o titular copia o nome do cliente na criação.
- Consulado `N/D` deixa de existir; funcionários antigos não entram.

## Autenticação
- Senha com hash + JWT (5a).
- Google OpenID Connect (5b): o token é verificado com a biblioteca do Google; domínio do Workspace e
  Client ID vêm de variáveis de ambiente. O usuário precisa existir e estar ativo em `usuarios`, senão 403.
