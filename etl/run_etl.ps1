# Runner del ETL Mercado Publico para el Programador de Tareas de Windows.
# 1. Asegura que PostgreSQL embebido este corriendo (puerto 5433).
# 2. Carga variables desde etl\.env.
# 3. Ejecuta fetch_licitaciones.py y registra log diario en logs\.

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $PSScriptRoot          # E:\licitaciones
$binPg = Join-Path $raiz ".pg\node_modules\@embedded-postgres\windows-x64\native\bin"
$pgData = Join-Path $raiz ".pgdata"
$pgLog = Join-Path $raiz ".pg\postgres.log"
$logDir = Join-Path $raiz "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Test-PgUp {
    return [bool](Get-NetTCPConnection -LocalPort 5433 -State Listen -ErrorAction SilentlyContinue)
}

if (-not (Test-PgUp)) {
    & (Join-Path $binPg "pg_ctl.exe") -D $pgData -l $pgLog start -o "-p 5433" | Out-Null
    $intentos = 0
    while (-not (Test-PgUp) -and $intentos -lt 15) {
        Start-Sleep -Seconds 1
        $intentos++
    }
}

# Variables de entorno desde etl\.env (formato CLAVE=valor)
Get-Content (Join-Path $PSScriptRoot ".env") | ForEach-Object {
    if ($_ -match "^\s*([A-Z_]+)\s*=\s*(.+)\s*$") {
        Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2]
    }
}

$log = Join-Path $logDir ("etl_{0:yyyyMMdd}.log" -f (Get-Date))
"===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') inicio =====" | Add-Content $log

try {
    & "C:\Python313\python.exe" (Join-Path $PSScriptRoot "fetch_licitaciones.py") *>> $log
    if ($LASTEXITCODE -ne 0) { throw "ETL termino con codigo $LASTEXITCODE" }
} catch {
    "ERROR: $_" | Add-Content $log
    exit 1
}
