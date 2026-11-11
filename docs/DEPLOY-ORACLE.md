# Colocar no ar na Oracle Cloud (plano gratuito)

Este guia sobe **a mesma aplicação** do `docs/DEPLOY.md` (Caddy + Next.js + API + PostgreSQL 18, via
`docker-compose.yml`), levando o banco atual, numa máquina do plano **Always Free** da Oracle. Boa parte é igual ao
guia da VPS comum; o que muda está concentrado na **criação da conta, da máquina e da rede**.

```
internet ──443──> Caddy (HTTPS automático) ──> web (Next.js) ──> api (FastAPI) ──> db (PostgreSQL 18)
                  só ele publica portas       rede interna do Docker, sem acesso de fora
```

> Os nomes de menus do painel da Oracle mudam de tempos em tempos e podem aparecer em português ou inglês; use a busca
> do painel (a lupa no topo) se não achar algum.

## Vale a pena? O que você precisa saber antes

Conferido na documentação oficial da Oracle (["Always Free Resources"](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm))
em novembro de 2026. **Os limites do plano gratuito mudam**: blogs mais antigos falam em 4 núcleos e 24 GB, mas hoje
o oficial é a metade disso.

| Item | O que o plano gratuito dá hoje |
| --- | --- |
| Máquina ARM (Ampere A1) | **2 núcleos e 12 GB de memória** no total (1 máquina de 2 núcleos, ou 2 de 1 núcleo). É a que usamos. |
| Máquina AMD "micro" | 1 GB de memória: **pequena demais** para esta aplicação (o build do front falha). Não use. |
| Disco | 200 GB no total (disco de boot + volumes), na região principal |
| Tráfego de saída | 10 TB por mês (sobra muito) |
| Backups de volume | 5 (da máquina inteira; não substituem o backup do banco) |
| Preço | R$ 0 dentro desses limites. Cartão de crédito é exigido no cadastro. |

### Os 4 cuidados que não dá para ignorar

1. **A Oracle pode parar máquinas "ociosas" do plano gratuito.** Pela regra oficial, a máquina é considerada ociosa se,
   durante **7 dias**, o uso de CPU (percentil 95), de rede e de memória ficarem **todos abaixo de 20%**. Este sistema,
   com poucos usuários, fica abaixo disso: **sem fazer nada, há risco real de a máquina ser parada**. A saída
   comumente usada é **converter a conta para "Pay As You Go"** (Parte 0, passo 4): segundo a Oracle, depois da
   conversão ela "só cobra o uso acima dos limites do Always Free". Mesmo assim, não achei no texto oficial a garantia
   explícita de que a conversão elimina a parada por ociosidade; acompanhe nos primeiros meses (Parte E).
2. **"Out of host capacity".** A Oracle às vezes não tem máquina ARM livre na região na hora de criar. Isso é comum e
   costuma passar tentando de novo mais tarde (de madrugada funciona melhor). Não há como pedir aumento no plano gratuito.
3. **A região principal não muda depois do cadastro.** Escolha **Brasil** (São Paulo `sa-saopaulo-1` ou Vinhedo
   `sa-vinhedo-1`): os dados de clientes (passaportes) ficam no país e o acesso é mais rápido. Fora do Brasil entra a
   questão de transferência internacional de dados da LGPD.
4. **Não há garantia de disponibilidade no plano gratuito** e a Oracle pode reclamar a máquina. O que protege você é o
   **backup do banco fora da Oracle** (Parte E). Sem ele, não suba dados reais.

### É muito mais complicado que uma VPS comum?

Não. Do começo ao fim são cerca de **2 a 3 horas na primeira vez**, a maior parte esperando verificação de conta e
build. As diferenças em relação ao `DEPLOY.md`:

| | VPS comum | Oracle |
| --- | --- | --- |
| Conta | já vem com a VPS | cadastro com cartão, verificação e escolha da região |
| Firewall | `ufw` na máquina | **Lista de segurança** da rede (no painel da Oracle), mais as regras da máquina |
| Usuário | cria o `deploy` | já existe o `ubuntu` (com sudo e sem root por SSH) |
| Processador | x86 | **ARM** (as imagens oficiais têm versão ARM; conferido, veja abaixo) |
| IP | fixo | reservar um IP público para não perdê-lo |

### Conferido para ARM (a máquina gratuita é ARM)

Construí e rodei **as duas imagens da aplicação em ARM64** (emulado no Docker do meu computador, em 10/11/2026):

- **API:** a imagem constrói e a aplicação importa e funciona em `aarch64` (hash de senha argon2, PostgreSQL, criptografia
  do login Google e fuso de Brasília).
- **Front:** o build completo do Next.js passa e o servidor responde `200` na tela de login, com os cabeçalhos de
  segurança, em Node 24 ARM64.
- As imagens oficiais `postgres:18`, `caddy:2`, `node:24-slim` e `python:3.14-slim` têm versão ARM, e o
  `package-lock.json` traz os binários nativos de ARM (Next, Tailwind e lightningcss).

**O que eu não consegui testar:** a pilha inteira numa máquina ARM de verdade da Oracle, nem o desempenho dela
(a emulação só prova que roda). O CI do projeto também só testa em x86. Se algo falhar só na Oracle, o sinal típico é
`exec format error` nos logs (imagem de outra arquitetura): me mande a mensagem.

## O que você precisa antes

- Um **domínio ou subdomínio** (ex.: `vistos.suaempresa.com.br`). Sem ele não há HTTPS válido nem login com o Google.
- Um **cartão de crédito** (a Oracle costuma fazer uma cobrança de verificação pequena, depois devolvida) e um **celular**
para o SMS.
- Uma **chave SSH**. No PowerShell do seu computador, se ainda não tem:

```powershell
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\oracle_concept -C "concept-oracle"
Get-Content $env:USERPROFILE\.ssh\oracle_concept.pub      # esta (a .pub) é a que você cola na Oracle
```

Nunca envie a chave privada (a sem `.pub`) para ninguém.

---

## Parte 0: criar a conta e proteger o bolso

**1. Cadastro.** Acesse https://www.oracle.com/br/cloud/free/ e clique em "Comece gratuitamente". Preencha os dados, o
cartão e confirme o SMS. **Home Region: escolha "Brazil East (Sao Paulo)" ou "Brazil Southeast (Vinhedo)"** e
não mude de ideia depois: não dá para trocar.

**2. Espere a conta ficar ativa** (e-mail de confirmação; pode levar de minutos a algumas horas).

**3. Alerta de gasto, antes de criar qualquer coisa.** No painel: **Faturamento e gerenciamento de custos
(Billing & Cost Management) → Orçamentos (Budgets) → Criar orçamento**. Valor **US$ 1** por mês, com alerta por e-mail
em 1% do valor. Se algo sair do gratuito sem você perceber, o e-mail chega logo.

**4. Converter para "Pay As You Go" (recomendado, pelo risco de parada por ociosidade).** Em **Faturamento →
Upgrade/Gerenciar pagamento**. Continua sem cobrança dentro dos limites do Always Free; só cobra o que passar deles. É
também o que reduz as falhas de "Out of host capacity" segundo relatos de usuários (isso não é garantido pela
Oracle). Se preferir testar sem converter, tudo abaixo funciona; só acompanhe se a máquina é parada (Parte E).

---

## Parte A: criar a máquina e abrir a rede

**1. Criar a instância.** Menu ☰ → **Computação (Compute) → Instâncias → Criar instância**.

- **Nome:** `concept-vistos`.
- **Imagem:** clique em "Alterar imagem" → **Canonical Ubuntu 24.04** (a versão `aarch64`, para ARM).
- **Forma (Shape):** "Alterar forma" → **Ampere → VM.Standard.A1.Flex** → **2 OCPUs** e **12 GB** de memória.
  (Mais que isso passa do gratuito.)
- **Rede:** "Criar nova rede virtual na nuvem" (VCN) com sub-rede pública, e **atribuir endereço IPv4 público: Sim**.
  **Não ative IPv6** (o Docker esconde o IP real de quem acessa por IPv6; veja o `DEPLOY.md`).
- **Chaves SSH:** "Colar chaves públicas" e cole o conteúdo do arquivo `oracle_concept.pub`.
- **Volume de boot:** marque "Especificar um tamanho de volume de boot personalizado" e coloque **100 GB** (cabe nos 200 GB
  gratuitos; o padrão de ~50 GB é pouco para imagens Docker e backups).

Clique em **Criar**. Em alguns minutos o estado vira "Em execução" e aparece o **IP público**.

> Se der **"Out of host capacity"**: tente de novo depois (de madrugada costuma funcionar), ou mais vezes ao longo do
> dia. Se der "limit exceeded", confira se você não escolheu mais de 2 OCPUs ou 12 GB.

**2. Reservar o IP (recomendado).** O IP "efêmero" some se a máquina for apagada, e o domínio apontaria para o vazio.
Menu ☰ → **Rede → Gerenciamento de IP → IPs públicos reservados → Reservar endereço IPv4**. Depois, na instância,
**Anexar VNICs → Endereços IPv4 → Editar**: tire o IP efêmero e atribua o reservado. (O limite gratuito de IPs
reservados eu só vi em relatos, não na documentação: se der erro de limite, siga com o efêmero e **não apague a
máquina**.)

**3. Abrir as portas 80 e 443 na rede da Oracle.** Esta é a etapa que mais engana: o painel da Oracle tem um firewall
próprio que bloqueia tudo, menos a porta 22. Vá em **Rede → Redes virtuais na nuvem → sua VCN → sua sub-rede pública →
Lista de segurança padrão → Adicionar regras de entrada**, e crie três:

| Origem (CIDR) | Protocolo | Porta de destino |
| --- | --- | --- |
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |
| `0.0.0.0/0` | UDP | `443` |

(A 80 serve para o certificado HTTPS ser emitido; a UDP 443 é o HTTP/3.) Deixe a regra da porta 22 como está.

**4. Apontar o domínio.** No painel do domínio, crie um registro **`A`** do subdomínio para o IP público. **Não crie
registro `AAAA`.** Confira com `nslookup vistos.suaempresa.com.br`.

**5. Entrar na máquina** (PowerShell do seu computador):

```powershell
ssh -i $env:USERPROFILE\.ssh\oracle_concept ubuntu@IP_PUBLICO
```

O usuário da Oracle para Ubuntu é `ubuntu` (já tem `sudo`). Na primeira vez responda `yes` à pergunta da impressão
digital. Confira que o acesso de root e por senha estão desligados (nas imagens da Oracle costumam vir assim):

```bash
sudo sshd -T | grep -Ei 'permitrootlogin|passwordauthentication'     # esperado: no / no (ou prohibit-password)
```

---

## Parte B: preparar a máquina

**1. Atualizações e proteção do SSH** (já como `ubuntu`):

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install unattended-upgrades fail2ban
sudo dpkg-reconfigure -plow unattended-upgrades     # responda "Sim"
```

**Não use o `ufw` aqui** (o guia da VPS comum usa): a imagem da Oracle já traz regras de firewall próprias e, segundo
relatos de usuários (e um alerta de um blog de desenvolvedores da Oracle), o `ufw` por cima pode deixar o site
inacessível. A proteção fica por conta da lista de segurança da Oracle (Parte A, passo 3) e
de o `docker-compose.yml` só publicar as portas 80 e 443.

**2. Instalar o Docker** (repositório oficial; o comando já escolhe a versão ARM sozinho):

```bash
sudo apt -y install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt update && sudo apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ubuntu      # saia (exit) e entre de novo no SSH para valer
docker run --rm hello-world         # teste
uname -m                            # deve mostrar: aarch64
```

**3. Baixar o projeto:**

```bash
git clone https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git concept
cd concept
```

(Repositório privado: use um _deploy key_ somente leitura, ou um token de acesso pessoal só de leitura.)

**4. Segredos de produção:**

```bash
cp .env.prod.example .env.prod
chmod 600 .env.prod
echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"    # copie a saída
echo "JWT_SECRET=$(openssl rand -hex 32)"           # copie a saída
nano .env.prod                                       # preencha DOMINIO, as duas linhas acima e (se usar) o Google
```

---

## Parte C: levar o banco atual para a Oracle

O banco vai **inteiro** (esquema, dados, usuários e a versão das migrations). O dump é lógico, então não importa que o
seu computador seja x86 e a máquina da Oracle seja ARM.

**No seu computador** (Docker Desktop aberto; **pare de usar o sistema local** antes, para nada mudar durante a
exportação):

```powershell
powershell -File deploy\exportar-dados.ps1          # gera concept.dump na raiz do projeto
scp -i $env:USERPROFILE\.ssh\oracle_concept concept.dump ubuntu@IP_PUBLICO:~/concept/
```

(Se o `pg_dump` for recusado pelo seu PostgreSQL local, veja a observação na Parte B do `docs/DEPLOY.md`.)

**Na máquina da Oracle**, restaurando num banco ainda vazio, **antes** de subir a API:

```bash
cd ~/concept
docker compose --env-file .env.prod up -d db
docker compose --env-file .env.prod exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' < concept.dump

# conferir: os números precisam bater com os do banco local
docker compose --env-file .env.prod exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select (select count(*) from clientes) clientes, (select count(*) from processos) processos, (select count(*) from usuarios) usuarios, (select version_num from alembic_version) migration"'

shred -u concept.dump        # apaga o dump da máquina (e apague a cópia do seu computador também)
```

Depois da restauração, **a máquina da Oracle é a fonte da verdade**: não exporte do computador de novo. Para refazer do
zero (só antes de usar de verdade): `docker compose --env-file .env.prod down -v` apaga o banco, e então repita esta parte.
O seu usuário administrador (e a senha dele) vem junto no dump.

---

## Parte D: subir tudo

```bash
cd ~/concept
docker compose --env-file .env.prod up -d --build      # a primeira vez demora 10 a 20 minutos (compila o front em ARM)
docker compose --env-file .env.prod ps                  # todos "running"/"healthy"
docker compose --env-file .env.prod logs -f caddy       # procure "certificate obtained successfully"
```

Abra `https://SEU_DOMINIO`: deve aparecer a tela de login com o cadeado.

**Conferir o IP real de quem acessa** (é o que vale para o limite de tentativas). Abra o site pelo celular em 4G e rode:

```bash
docker compose --env-file .env.prod logs --tail=30 api | grep '"ip"'
```

Tem que aparecer o IP público do celular. Se só aparecer `172.30.0.1` (endereço interno do Docker), o IP real não está
chegando: confirme que não há `AAAA` no DNS e que o acesso é por IPv4.

**Login com o Google:** no Google Cloud Console, no cliente OAuth, adicione só o **URI de redirecionamento**:
`https://SEU_DOMINIO/api/auth/google/callback`. Preencha `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (e, se quiser,
`GOOGLE_ALLOWED_DOMAIN`) no `.env.prod` e rode `docker compose --env-file .env.prod up -d`. Enquanto o app do Google
estiver em modo **Teste**, só entram os e-mails listados em "Usuários de teste", que também precisam estar em Usuários
no sistema.

### Se o site não abrir, mas o `ps` mostra tudo saudável

1. **Lista de segurança** da Oracle (Parte A, passo 3): confirme as regras 80 e 443.
2. **Firewall da máquina.** A imagem da Oracle traz uma regra que recusa o que não foi liberado. Veja:

   ```bash
   sudo iptables -L INPUT -n --line-numbers
   ```

   Se houver uma linha `REJECT` antes das suas regras, insira as portas **antes dela** (troque `5` pelo número da linha
   do `REJECT`), e salve para sobreviver a reinício:

   ```bash
   sudo iptables -I INPUT 5 -p tcp --dport 80 -j ACCEPT
   sudo iptables -I INPUT 5 -p tcp --dport 443 -j ACCEPT
   sudo iptables -I INPUT 5 -p udp --dport 443 -j ACCEPT
   sudo apt -y install iptables-persistent && sudo netfilter-persistent save
   ```

   (Receita de guias da comunidade; a ordem das regras importa, por isso o `-I` com o número da linha.)
3. **DNS:** `nslookup SEU_DOMINIO` tem que devolver o IP público da máquina.

---

## Parte E: no dia a dia

| Tarefa | Comando (na pasta `~/concept`) |
| --- | --- |
| Atualizar para a versão nova | `git pull && docker compose --env-file .env.prod up -d --build` |
| Ver logs da API | `docker compose --env-file .env.prod logs -f --tail=100 api` |
| Ver o estado | `docker compose --env-file .env.prod ps` |
| Reiniciar um serviço | `docker compose --env-file .env.prod restart api` |
| Ver uso de memória e CPU | `docker stats --no-stream` |

As migrations rodam sozinhas quando a API sobe. **Faça um backup antes de atualizar** quando a versão tiver migration nova.

### Backup (obrigatório: a máquina gratuita pode ser parada ou perdida)

```bash
chmod +x deploy/backup.sh
./deploy/backup.sh                       # teste uma vez
crontab -e                               # e acrescente a linha abaixo (todo dia às 03:00)
0 3 * * * cd /home/ubuntu/concept && ./deploy/backup.sh >> /home/ubuntu/backup.log 2>&1
```

Os backups ficam em `~/concept/backups` (14 dias). **Backup só dentro da Oracle não é backup.** Copie para o seu
computador (ou outro lugar fora da Oracle) com frequência:

```powershell
scp -i $env:USERPROFILE\.ssh\oracle_concept "ubuntu@IP_PUBLICO:~/concept/backups/concept-*.dump" C:\backups-concept\
```

Os dumps têm dados de clientes: guarde em local protegido. Uma camada extra, **que não substitui** o `pg_dump`: o
painel da Oracle permite um backup do volume de boot inteiro (5 grátis em **Armazenamento → Volumes de boot →
Backups**), útil para recriar a máquina do jeito que estava. **Teste a restauração de um dump uma vez** (veja o
`DEPLOY.md`): um backup nunca restaurado é uma suposição.

### Vigiar a "ociosidade" (Parte 0, cuidado 1)

- Uma vez por semana, olhe se a instância está **"Em execução"** (Computação → Instâncias). Se estiver "Parada", é só
  clicar em **Iniciar** (se a forma ainda estiver disponível na região) e conferir `docker compose ps`.
- O `restart: unless-stopped` do compose sobe tudo sozinho quando a máquina volta.
- Configure um monitor externo gratuito (ex.: UptimeRobot) em `https://SEU_DOMINIO/login`: ele avisa se o site cair.

### Cuidados

- **Não apague a instância** sem antes ter um backup fora da Oracle e sem saber que o IP reservado continua seu.
- Não rode `docker compose down -v` por engano (o `-v` apaga o banco) nem perca o volume `caddy_dados` (certificados).
- Fique dentro do gratuito: **2 OCPUs, 12 GB, 200 GB de disco no total**. Recursos com o selo "Always Free" no painel são os
  seguros; o alerta de gasto da Parte 0 avisa se algo começar a cobrar.
- Os limites do plano gratuito mudam. Antes de criar a conta, releia a página oficial citada no topo.
