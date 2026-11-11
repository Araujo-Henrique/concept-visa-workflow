# Colocar no ar numa VPS (Docker + HTTPS)

Como fica:

```
internet ──443──> Caddy (HTTPS automático) ──> web (Next.js) ──> api (FastAPI) ──> db (PostgreSQL 18)
                  só ele publica portas       rede interna do Docker, sem acesso de fora
```

O que vai para o GitHub: `Dockerfile.api`, `web/Dockerfile`, `docker-compose.yml`, `deploy/` e este guia.
O que **nunca** vai: `.env.prod` (segredos) e `concept.dump` (dados de clientes). Esses dois você leva por `scp`.

## O que você precisa antes

- Uma VPS com **Ubuntu 24.04**, 2 vCPU, 4 GB de RAM e 40 GB de disco (com 2 GB o build do front pode falhar).
- Um **domínio ou subdomínio** (ex.: `vistos.suaempresa.com.br`). Sem ele não há HTTPS válido nem login com o Google.
- Sua chave SSH pública (se não tem: `ssh-keygen -t ed25519` no seu computador).

---

## Parte A: preparar a VPS

**1. DNS.** No painel do domínio, crie um registro `A` do subdomínio apontando para o IP da VPS. Confira com
`nslookup vistos.suaempresa.com.br` antes de seguir (a propagação pode levar minutos).

**Não crie registro `AAAA` (IPv6).** O Docker esconde o IP real de quem acessa por IPv6 (todos apareceriam com o
mesmo endereço interno), e o limite de tentativas de login passaria a valer para todos juntos. Só com o `A`, todo
mundo entra por IPv4 e o IP real é preservado. Se o provedor da VPS já criou um `AAAA` sozinho, apague-o.

**2. Primeiro acesso e usuário próprio.** O provedor entrega acesso como `root`. Troque por um usuário comum:

```bash
ssh root@IP_DA_VPS
adduser deploy                      # defina uma senha forte (só serve para o sudo)
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh && chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
```

**Abra outro terminal e teste** `ssh deploy@IP_DA_VPS` antes de continuar. Só depois, na sessão root, desligue o
acesso de root e por senha:

```bash
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
```

(Em algumas imagens há arquivos em `/etc/ssh/sshd_config.d/` que repetem essas opções: confira com `grep -r Password /etc/ssh/sshd_config.d/`.)

**3. Atualizações e firewall** (já como `deploy`):

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install unattended-upgrades fail2ban ufw
sudo dpkg-reconfigure -plow unattended-upgrades     # responda "Sim": segurança automática

sudo ufw default deny incoming
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw enable
```

O `fail2ban` já vem com a proteção do SSH ligada. Obs.: o Docker mexe no firewall por conta própria; por isso o
`docker-compose.yml` só publica as portas 80 e 443 (a API e o banco não têm porta aberta para fora).

**4. Instalar o Docker** (repositório oficial):

```bash
sudo apt -y install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt update && sudo apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker deploy      # saia e entre de novo no SSH para valer
docker run --rm hello-world         # teste
```

**5. Baixar o projeto:**

```bash
git clone https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git concept
cd concept
```

(Repositório privado: use um _deploy key_ somente leitura, ou um token de acesso pessoal com permissão só de leitura.)

**6. Segredos de produção:**

```bash
cp .env.prod.example .env.prod
chmod 600 .env.prod
echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"    # copie a saída
echo "JWT_SECRET=$(openssl rand -hex 32)"           # copie a saída
nano .env.prod                                       # preencha DOMINIO, as duas linhas acima e (se usar) o Google
```

---

## Parte B: levar os dados já tratados para a VPS

O banco vai **inteiro** (esquema, dados, usuários e a versão das migrations), então o que você tratou chega igual.

**No seu computador** (Docker Desktop aberto; **pare de usar o sistema local** antes, para nada mudar durante a exportação):

```powershell
powershell -File deploy\exportar-dados.ps1          # gera concept.dump na raiz do projeto
scp concept.dump deploy@IP_DA_VPS:~/concept/
```

Se o `pg_dump` falhar com "connection refused" ou "no pg_hba.conf entry", é o PostgreSQL do seu computador recusando a
conexão que vem do contêiner Docker. Em `postgresql.conf` use `listen_addresses = '*'` e, em `pg_hba.conf`, libere a
rede do Docker (ex.: `host all all 172.16.0.0/12 scram-sha-256`); reinicie o PostgreSQL, rode de novo e **desfaça
essas duas linhas depois**. (Alternativa: `pg_dump -Fc --no-owner --no-privileges -f concept.dump "$DATABASE_URL"`
direto no seu computador, se tiver o `pg_dump` 18 instalado.)

**Na VPS**, restaurando num banco ainda vazio, **antes** de subir a API (a API cria tabelas ao subir, e a restauração
precisa de banco vazio):

```bash
cd ~/concept
docker compose --env-file .env.prod up -d db
docker compose --env-file .env.prod exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' < concept.dump

# conferir: os números precisam bater com os do banco local
docker compose --env-file .env.prod exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select (select count(*) from clientes) clientes, (select count(*) from processos) processos, (select count(*) from usuarios) usuarios, (select version_num from alembic_version) migration"'

shred -u concept.dump        # apaga o dump da VPS (e apague a cópia do seu computador também)
```

Depois da restauração, **a VPS é a fonte da verdade**: não exporte do computador de novo e sobrescreva. Se precisar
refazer do zero (antes de usar de verdade): `docker compose --env-file .env.prod down -v` apaga o banco da VPS (cuidado: só faça se tiver certeza) e repita a Parte B.

Seu usuário administrador (e a senha dele) vem junto no dump: não é preciso criar outro.

---

## Parte C: subir tudo

```bash
cd ~/concept
docker compose --env-file .env.prod up -d --build      # a primeira vez demora (compila o front)
docker compose --env-file .env.prod ps                  # todos "running"/"healthy"
docker compose --env-file .env.prod logs -f caddy       # procure "certificate obtained successfully"
```

Abra `https://SEU_DOMINIO`: deve aparecer a tela de login com o cadeado.

**Confira se a API vê o IP real de quem acessa** (é ele que vale para o limite de tentativas). Abra o site pelo
celular (com o Wi-Fi desligado, em 4G) e rode:

```bash
docker compose --env-file .env.prod logs --tail=30 api | grep '"ip"'
```

Tem que aparecer o IP público do celular. Se só aparecer `172.30.0.1` (endereço interno do Docker), o IP real não está
chegando: confirme que não há registro `AAAA` no DNS e que o acesso é por IPv4.

**Login com o Google:** no Google Cloud Console, no cliente OAuth (tipo "Aplicativo da Web"), adicione só o
**URI de redirecionamento autorizado**, idêntico e com `https`:

```
https://SEU_DOMINIO/api/auth/google/callback
```

Não precisa de "Origem JavaScript autorizada": o login roda no servidor, não no navegador. Enquanto o app estiver em
modo **Teste** (Google Auth Platform → Público-alvo), só entram os e-mails listados em "Usuários de teste", e todos
eles também precisam estar cadastrados em Usuários no sistema. O Google pode levar alguns minutos para valer o
endereço novo.

E preencha `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (e, se quiser, `GOOGLE_ALLOWED_DOMAIN`) no `.env.prod`; depois
`docker compose --env-file .env.prod up -d` para aplicar.

---

## Parte D: no dia a dia

| Tarefa | Comando (na pasta `~/concept`) |
| --- | --- |
| Atualizar para a versão nova | `git pull && docker compose --env-file .env.prod up -d --build` |
| Ver logs da API | `docker compose --env-file .env.prod logs -f --tail=100 api` |
| Ver o estado | `docker compose --env-file .env.prod ps` |
| Reiniciar um serviço | `docker compose --env-file .env.prod restart api` |

As migrations rodam sozinhas quando a API sobe. **Faça um backup antes de atualizar** quando a versão tiver migration nova.

### Backup

```bash
chmod +x deploy/backup.sh
./deploy/backup.sh                       # teste uma vez
crontab -e                               # e acrescente a linha abaixo (todo dia às 03:00)
0 3 * * * cd /home/deploy/concept && ./deploy/backup.sh >> /home/deploy/backup.log 2>&1
```

Os backups ficam em `~/concept/backups` (14 dias). **Backup só dentro da VPS não é backup**: se a máquina for perdida, vai
junto. Copie para outro lugar, por exemplo para o seu computador:

```powershell
scp "deploy@IP_DA_VPS:~/concept/backups/concept-*.dump" C:\backups-concept\
```

(ou configure `rclone` para um armazenamento na nuvem; peça e eu monto). Os dumps têm dados de clientes: guarde em
local protegido.

**Restaurar um backup** (num banco vazio): mesmo comando da Parte B, apontando para o arquivo do backup. **Teste isso
uma vez** num servidor de teste: um backup que nunca foi restaurado é uma suposição. Um jeito simples, sem outra
máquina: `docker run --rm -d --name teste-restore -e POSTGRES_PASSWORD=x postgres:18`, restaure o dump nele com
`pg_restore`, confira as contagens e apague com `docker rm -f teste-restore`.

### Cuidados

- Não perca o volume `caddy_dados` (certificados) nem rode `docker compose down -v` por engano: o `-v` apaga o banco.
- `docker system prune` sem cuidado também pode apagar coisas; prefira não usar com `--volumes`.
- Para saber se está de pé de fora, use um monitor gratuito (ex.: UptimeRobot) apontando para `https://SEU_DOMINIO/login`.
