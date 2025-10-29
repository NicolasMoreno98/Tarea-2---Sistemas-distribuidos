# Script para ejecutar experimento y monitorear resultados automáticamente
param(
    [int]$NumRequests = 100
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "EJECUTAR EXPERIMENTO CON MONITOREO" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Configuracion:" -ForegroundColor Yellow
Write-Host "  * Numero de requests: $NumRequests`n" -ForegroundColor White

# Preguntar confirmación
$confirm = Read-Host "Desea continuar? (s/n)"
if ($confirm -ne "s" -and $confirm -ne "S") {
    Write-Host "`n[CANCELADO] Operacion cancelada`n" -ForegroundColor Red
    exit
}

# Paso 1: Reiniciar traffic generator
Write-Host "`n[1] Reiniciando traffic generator..." -ForegroundColor Green
Set-Location "d:\U\Sistemas Distribuidos\Docker\yahoo_llm_project"
docker-compose -f docker-compose-tarea2.yml restart traffic-generator
Write-Host "[OK] Traffic generator reiniciado`n" -ForegroundColor Green

# Paso 2: Esperar un momento
Write-Host "Esperando 3 segundos para que inicie..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Paso 3: Iniciar monitor
Write-Host "`n[2] Iniciando monitor del experimento...`n" -ForegroundColor Green
Set-Location "d:\U\Sistemas Distribuidos\Docker\yahoo_llm_project\scripts"
python monitor_experiment.py

Write-Host "`nProceso completado`n" -ForegroundColor Cyan
