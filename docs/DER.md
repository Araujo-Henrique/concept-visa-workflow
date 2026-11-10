# Diagrama entidade-relacionamento (DER)

> Todos os dados deste repositório são fictícios. O GitHub desenha o diagrama abaixo sozinho.
> Fonte da verdade: [app/models.py](../app/models.py) e as migrations em [migrations/versions/](../migrations/versions/).

```mermaid
erDiagram
    perfis ||--o{ usuarios : "tem"
    usuarios ||--o{ auditoria_usuarios : "sofre mudancas"
    usuarios ||--o{ auditoria_usuarios : "faz mudancas"
    usuarios ||--o{ processos : "cria"
    usuarios ||--o{ eventos : "registra"
    usuarios ||--o{ processo_obt : "orienta"

    clientes ||--o{ processos : "tem"
    situacoes ||--o{ processos : "situacao valida do tipo"
    processos ||--o| processos : "nova tentativa de"

    processos ||--o| processo_obt : "detalhe OBT"
    processos ||--o| processo_ren : "detalhe REN"
    processos ||--o| processo_pass : "detalhe PASS"

    processos ||--|{ solicitantes : "agrupa"
    solicitantes ||--o{ formularios_ds160 : "preenche"
    processos ||--|{ eventos : "historico"
    usuarios ||--o{ chaves_idempotencia : "envia"

    perfis {
        int id PK
        string nome UK "admin, atendente, leitor"
    }
    usuarios {
        int id PK
        string nome
        string email UK "unico sem diferenciar maiusculas"
        string senha_hash "nulo = so Google"
        int perfil_id FK
        bool ativo
    }
    auditoria_usuarios {
        int id PK
        int usuario_id FK "quem sofreu"
        int feito_por_id FK "quem fez"
        string campo "perfil, ativo, nome, senha"
        text valor_anterior
        text valor_novo
        datetime criado_em
    }
    auditoria {
        bigint id PK
        string tabela "clientes, processos, processo_obt/ren/pass, solicitantes, formularios_ds160"
        int registro_id "sem FK: o rastro sobrevive a remocao"
        int processo_id "contexto, mesmo se ja apagado"
        int cliente_id "contexto, mesmo se ja apagado"
        string acao "criou, editou, apagou"
        jsonb antes
        jsonb depois
        int usuario_id "sem FK"
        string requisicao "o mesmo codigo do log"
        string origem "api, seed, importacao, banco"
        bigint transacao
        datetime criado_em
    }
    chaves_idempotencia {
        int id PK
        int usuario_id FK
        string chave "unica por usuario"
        string escopo "metodo e rota"
        string impressao "sha256 do corpo"
        int status "nulo = em andamento"
        text corpo "resposta guardada"
        datetime criado_em
    }
    clientes {
        int id PK
        string nome UK "unico sem diferenciar maiusculas"
        string email
        string telefone
        string grupo
    }
    situacoes {
        string tipo PK
        string nome PK
    }
    processos {
        int id PK
        string tipo "OBT, REN ou PASS"
        int cliente_id FK
        string situacao FK "com tipo: FK composta"
        int processo_anterior_id FK
        text observacao
        int criado_por_id FK
        datetime criado_em
        datetime atualizado_em
    }
    processo_obt {
        int processo_id PK, FK
        string tipo FK "sempre OBT"
        string consulado "opcional"
        string monitoramento
        date data_casv
        date data_entrevista
        date data_vencimento_taxa
        string status_rascunho
        string orientacao
        date orientacao_data
        int orientacao_por_id FK
        string codigo_rastreio
    }
    processo_ren {
        int processo_id PK, FK
        string tipo FK "sempre REN"
        string consulado "obrigatorio se houver data_casv"
        date data_casv
        date data_despacho "gerada: data_casv - 7"
        string docs
        string status_rascunho
        text endereco
        string codigo_rastreio
    }
    processo_pass {
        int processo_id PK, FK
        string tipo FK "sempre PASS"
        date data_pf
        date prazo_pf
    }
    solicitantes {
        int id PK
        int processo_id FK
        string nome
        bool titular "um so por processo"
        string resultado "Processando, Aprovado, Negado"
    }
    formularios_ds160 {
        int id PK
        int solicitante_id FK
        string codigo UK "AA00 + 6 alfanumericos"
        string status
        text observacao
    }
    eventos {
        int id PK
        int processo_id FK
        int usuario_id FK
        string tipo "criado, situacao_alterada, reaberto"
        string situacao_anterior
        string situacao_nova
        text motivo "obrigatorio se reaberto"
        datetime criado_em
    }
```

Além das tabelas, existe a **view `vw_painel_processos`** (migration 0003, ampliada na 0005): uma linha por
processo, no formato da planilha da operação. Ela junta clientes, o detalhe do tipo, os solicitantes (contados
e resumidos num resultado geral) e a orientação. A rota `GET /painel` lê dela.

## Como ler as relações

- **Herança de tabela unida.** `processos` guarda o que é comum; `processo_obt`, `processo_ren` e
  `processo_pass` guardam o que é de cada tipo. A FK composta `(processo_id, tipo)` impede, por exemplo, um
  detalhe de REN ligado a um processo OBT.
- **FK composta para a situação.** `(tipo, situacao)` aponta para `situacoes`: o banco, e não o código, decide
  quais situações existem para cada tipo (`Pix` só em passaporte, `Entrevista` só em renovação).
- **1:N.** A tabela do lado "muitos" guarda o id do lado "um" (`solicitantes.processo_id`). A quantidade de
  solicitantes é contada, não armazenada.
- **Auditoria sem chave estrangeira.** `auditoria` é preenchida por trigger em cada tabela auditada e não
  aponta para elas: quando um cliente é apagado, o histórico dele continua lá (`cliente_id` e `processo_id`
  guardam o contexto). Só aceita INSERT. Fica fora do diagrama de relações de propósito.
- **Auto-relação.** `processos.processo_anterior_id` liga uma nova tentativa à negativa anterior do mesmo cliente.
