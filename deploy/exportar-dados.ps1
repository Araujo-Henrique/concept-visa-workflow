# Exporta o banco LOCAL (o do seu .env) para concept.dump, para levar à VPS.
# Roda o pg_dump dentro de um contêiner postgres:18 (a mesma versão do servidor local e da VPS),
# então não precisa instalar nada além do Docker Desktop (aberto).
#
#   powershell -File deploy\exportar-dados.ps1
#
# O concept.dump tem dados de clientes: NUNCA vai para o Git (o .gitignore já ignora *.dump).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$linha = Get-Content .env | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
if (-not $linha) { throw "DATABASE_URL não encontrada no .env" }
$url = ($linha -replace '^DATABASE_URL=', '').Trim()
$url = $url -replace '^postgresql\+psycopg://', 'postgresql://'
# de dentro do contêiner, "localhost" é o próprio contêiner: o computador é host.docker.internal
$url = $url -replace '@(localhost|127\.0\.0\.1)([:/])', '@host.docker.internal$2'

$env:URL_DO_BANCO = $url   # passa por variável de ambiente: a senha não aparece na linha de comando
docker run --rm -e URL_DO_BANCO -v "${PWD}:/saida" postgres:18 `
    sh -c 'pg_dump "$URL_DO_BANCO" -Fc --no-owner --no-privileges -f /saida/concept.dump'
Remove-Item Env:URL_DO_BANCO
if ($LASTEXITCODE -ne 0) { throw "pg_dump falhou" }

$tamanho = [math]::Round((Get-Item concept.dump).Length / 1MB, 2)
Write-Host "Pronto: concept.dump ($tamanho MB). Envie com scp (docs/DEPLOY.md) e apague a cópia local depois."
