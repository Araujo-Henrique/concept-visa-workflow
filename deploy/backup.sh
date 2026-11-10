#!/usr/bin/env bash
# Backup diário do banco (formato custom do pg_dump). Rode na VPS, na pasta do projeto:
#   ./deploy/backup.sh            (ou pelo cron: veja docs/DEPLOY.md)
# Guarda em ./backups e apaga os de mais de 14 dias. Copiar para FORA da VPS é por sua conta (docs/DEPLOY.md).
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
. ./.env.prod
set +a

pasta="backups"
mkdir -p "$pasta"
chmod 700 "$pasta"
arquivo="$pasta/concept-$(date +%F-%H%M).dump"

docker compose --env-file .env.prod exec -T db \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner > "$arquivo.parcial"
mv "$arquivo.parcial" "$arquivo"   # só aparece com o nome final se o dump terminou inteiro
chmod 600 "$arquivo"

find "$pasta" -name 'concept-*.dump' -mtime +14 -delete
echo "Backup salvo em $arquivo ($(du -h "$arquivo" | cut -f1))"
