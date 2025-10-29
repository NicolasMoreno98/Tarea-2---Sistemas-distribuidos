# Script para ejecutar experimento de cache hits vs cache miss
# Compara el rendimiento con preguntas nuevas vs preguntas cacheadas

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   EXPERIMENTO DE CACHE: 100 PREGUNTAS" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Función para esperar a que el traffic_generator termine
function Wait-TrafficGenerator {
    Write-Host "Esperando a que traffic_generator complete..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    
    $maxWait = 300  # 5 minutos máximo
    $elapsed = 0
    
    while ($elapsed -lt $maxWait) {
        $status = docker ps -a --filter "name=traffic_generator" --format "{{.Status}}"
        if ($status -match "Exited") {
            Write-Host "✓ Traffic generator completado" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 5
        $elapsed += 5
        if ($elapsed % 30 -eq 0) {
            Write-Host "  Esperando... ($elapsed segundos)" -ForegroundColor Gray
        }
    }
    
    Write-Host "✗ Timeout esperando traffic_generator" -ForegroundColor Red
    return $false
}

# Función para obtener estadísticas
function Get-ExperimentStats {
    Write-Host ""
    Write-Host "📊 ESTADÍSTICAS DEL EXPERIMENTO:" -ForegroundColor Cyan
    
    # Kafka stats
    Write-Host ""
    Write-Host "Kafka Topics:" -ForegroundColor Yellow
    docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list | Where-Object { $_ -match "questions-pending|llm-responses|validated" } | ForEach-Object {
        $topic = $_
        $count = docker exec kafka kafka-run-class kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic $topic --time -1 | Measure-Object -Sum -Property { [int]($_.Split(':')[-1]) } | Select-Object -ExpandProperty Sum
        Write-Host "  - $topic`: $count mensajes" -ForegroundColor White
    }
    
    # Database stats
    Write-Host ""
    Write-Host "Base de Datos:" -ForegroundColor Yellow
    docker exec postgres_db psql -U user -d yahoo_db -t -c "SELECT COUNT(*) FROM responses;" | ForEach-Object {
        Write-Host "  - Total responses: $($_.Trim())" -ForegroundColor White
    }
    
    # Logs del traffic_generator (últimas líneas con resumen)
    Write-Host ""
    Write-Host "Resumen Traffic Generator:" -ForegroundColor Yellow
    docker logs traffic_generator --tail 20 | Select-String -Pattern "Cache hits|Async processed|Total|Resultado" | ForEach-Object {
        Write-Host "  $_" -ForegroundColor White
    }
}

# ========================================
# EXPERIMENTO 1: PREGUNTAS NUEVAS (primeras 20k de train.csv)
# ========================================

Write-Host ""
Write-Host "=== EXPERIMENTO 1: PREGUNTAS NUEVAS ===" -ForegroundColor Magenta
Write-Host "Configuración: USE_CACHED_IDS=false (primeras 20k de train.csv)" -ForegroundColor Gray
Write-Host ""

# Detener contenedores existentes
Write-Host "Deteniendo contenedores..." -ForegroundColor Yellow
docker-compose -f docker-compose-tarea2.yml down 2>$null

# Asegurar que USE_CACHED_IDS=false
$content = Get-Content docker-compose-tarea2.yml -Raw
$content = $content -replace 'USE_CACHED_IDS=true', 'USE_CACHED_IDS=false'
Set-Content docker-compose-tarea2.yml -Value $content

# Rebuild traffic_generator
Write-Host "Reconstruyendo traffic_generator..." -ForegroundColor Yellow
docker-compose -f docker-compose-tarea2.yml build traffic-generator 2>&1 | Out-Null

# Iniciar sistema
Write-Host "Iniciando sistema..." -ForegroundColor Yellow
docker-compose -f docker-compose-tarea2.yml up -d

# Esperar a que todo esté listo
Write-Host "Esperando a que los servicios estén listos (30s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Esperar resultados
if (Wait-TrafficGenerator) {
    Get-ExperimentStats
    
    # Guardar resultados
    Write-Host ""
    Write-Host "Guardando resultados del Experimento 1..." -ForegroundColor Yellow
    docker logs traffic_generator > "experiment1_nuevas_preguntas.log"
    Write-Host "✓ Guardado en experiment1_nuevas_preguntas.log" -ForegroundColor Green
}

# ========================================
# EXPERIMENTO 2: PREGUNTAS CACHEADAS
# ========================================

Write-Host ""
Write-Host ""
Write-Host "=== EXPERIMENTO 2: PREGUNTAS CACHEADAS ===" -ForegroundColor Magenta
Write-Host "Configuración: USE_CACHED_IDS=true (preguntas ya en DB/cache)" -ForegroundColor Gray
Write-Host ""

# Detener contenedores
Write-Host "Deteniendo contenedores..." -ForegroundColor Yellow
docker-compose -f docker-compose-tarea2.yml down 2>$null

# Cambiar a USE_CACHED_IDS=true
$content = Get-Content docker-compose-tarea2.yml -Raw
$content = $content -replace 'USE_CACHED_IDS=false', 'USE_CACHED_IDS=true'
Set-Content docker-compose-tarea2.yml -Value $content

# Rebuild traffic_generator
Write-Host "Reconstruyendo traffic_generator..." -ForegroundColor Yellow
docker-compose -f docker-compose-tarea2.yml build traffic-generator 2>&1 | Out-Null

# Iniciar sistema
Write-Host "Iniciando sistema..." -ForegroundColor Yellow
docker-compose -f docker-compose-tarea2.yml up -d

# Esperar a que todo esté listo
Write-Host "Esperando a que los servicios estén listos (30s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Esperar resultados
if (Wait-TrafficGenerator) {
    Get-ExperimentStats
    
    # Guardar resultados
    Write-Host ""
    Write-Host "Guardando resultados del Experimento 2..." -ForegroundColor Yellow
    docker logs traffic_generator > "experiment2_preguntas_cacheadas.log"
    Write-Host "✓ Guardado en experiment2_preguntas_cacheadas.log" -ForegroundColor Green
}

# ========================================
# COMPARACIÓN FINAL
# ========================================

Write-Host ""
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   COMPARACIÓN DE EXPERIMENTOS" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "EXPERIMENTO 1 (Preguntas Nuevas):" -ForegroundColor Yellow
Get-Content "experiment1_nuevas_preguntas.log" | Select-String -Pattern "Cache hits|Async processed|Total|esperado" | ForEach-Object {
    Write-Host "  $_" -ForegroundColor White
}

Write-Host ""
Write-Host "EXPERIMENTO 2 (Preguntas Cacheadas):" -ForegroundColor Yellow
Get-Content "experiment2_preguntas_cacheadas.log" | Select-String -Pattern "Cache hits|Async processed|Total|esperado" | ForEach-Object {
    Write-Host "  $_" -ForegroundColor White
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   EXPERIMENTO COMPLETADO" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Logs guardados en:" -ForegroundColor Green
Write-Host "  - experiment1_nuevas_preguntas.log" -ForegroundColor White
Write-Host "  - experiment2_preguntas_cacheadas.log" -ForegroundColor White
Write-Host ""

# Restaurar configuración original
$content = Get-Content docker-compose-tarea2.yml -Raw
$content = $content -replace 'USE_CACHED_IDS=true', 'USE_CACHED_IDS=false'
Set-Content docker-compose-tarea2.yml -Value $content
