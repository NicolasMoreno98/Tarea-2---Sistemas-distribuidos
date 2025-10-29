# Script de inicio completo para Tarea 2 con Flink

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Sistema Yahoo LLM - Tarea 2 con Apache Flink             ║" -ForegroundColor Cyan
Write-Host "║  Compilando, desplegando y levantando todos los servicios ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"
$startTime = Get-Date

# Paso 1: Compilar Flink Job
Write-Host "📦 [1/5] Compilando Flink Job con Maven (en Docker)..." -ForegroundColor Yellow
Push-Location "$PSScriptRoot"

if (-not (Test-Path "flink-job\pom.xml")) {
    Write-Host "❌ Error: pom.xml no encontrado" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "   Descargando dependencias y compilando..." -ForegroundColor Gray
Write-Host "   (Primera vez puede tardar 2-3 minutos descargando JARs)" -ForegroundColor Gray

docker run --rm `
    -v "$PSScriptRoot\flink-job:/app" `
    -w /app `
    maven:3.9-eclipse-temurin-11 `
    mvn clean package -DskipTests 2>&1 | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al compilar Flink job" -ForegroundColor Red
    Write-Host "   Intenta manualmente: .\compile-flink-job.ps1" -ForegroundColor Yellow
    Pop-Location
    exit 1
}

if (-not (Test-Path "flink-job\target\flink-score-validator-1.0.jar")) {
    Write-Host "❌ Error: JAR no generado" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "✅ Flink job compilado exitosamente" -ForegroundColor Green
Write-Host "   JAR: flink-job\target\flink-score-validator-1.0.jar" -ForegroundColor Gray
Pop-Location

# Paso 2: Detener contenedores existentes
Write-Host ""
Write-Host "🛑 [2/5] Deteniendo contenedores existentes..." -ForegroundColor Yellow
docker-compose -f docker-compose-tarea2.yml down 2>&1 | Out-Null
Write-Host "✅ Contenedores detenidos" -ForegroundColor Green

# Paso 3: Levantar servicios con docker-compose
Write-Host ""
Write-Host "🚀 [3/5] Levantando servicios con docker-compose..." -ForegroundColor Yellow
Write-Host "   (Esto puede tardar 2-3 minutos)" -ForegroundColor Gray

docker-compose -f docker-compose-tarea2.yml up -d --build 2>&1 | Out-Null

# Esperar a que Zookeeper esté listo (conocido delay)
Write-Host "⏳ Esperando healthchecks..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Iniciar servicios manualmente si es necesario
Write-Host "🔧 Iniciando servicios dependientes..." -ForegroundColor Yellow
docker start kafka_broker 2>&1 | Out-Null
Start-Sleep -Seconds 15
docker start kafka_init storage_service yahoo_llm_project-llm-consumer-1 yahoo_llm_project-llm-consumer-2 retry_overload_consumer retry_quota_consumer score_validator kafka_ui traffic_generator 2>&1 | Out-Null
Start-Sleep -Seconds 10

# Iniciar Flink
docker start flink_jobmanager flink_taskmanager 2>&1 | Out-Null
Start-Sleep -Seconds 10

Write-Host "✅ Servicios levantados" -ForegroundColor Green

# Paso 4: Verificar servicios
Write-Host ""
Write-Host "🔍 [4/5] Verificando servicios..." -ForegroundColor Yellow

$containers = docker ps --format "{{.Names}}" | Where-Object { $_ -match "yahoo|postgres|redis|kafka|flink|zookeeper" }
$runningCount = ($containers | Measure-Object).Count

Write-Host "   Contenedores corriendo: $runningCount" -ForegroundColor Gray

if ($runningCount -lt 14) {
    Write-Host "⚠️  Advertencia: Solo $runningCount de 14 servicios esperados" -ForegroundColor Yellow
} else {
    Write-Host "✅ Todos los servicios están UP" -ForegroundColor Green
}

# Paso 5: Desplegar Flink Job
Write-Host ""
Write-Host "📤 [5/5] Desplegando Flink Job..." -ForegroundColor Yellow

# Esperar a que Flink JobManager esté completamente listo
Write-Host "   Esperando a que Flink esté listo..." -ForegroundColor Gray
Start-Sleep -Seconds 15

# Desplegar el job
$deployOutput = docker exec flink_jobmanager flink run -d /opt/flink-job/target/flink-score-validator-1.0.jar 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Flink job desplegado exitosamente" -ForegroundColor Green
} else {
    Write-Host "⚠️  Advertencia: No se pudo desplegar el job automáticamente" -ForegroundColor Yellow
    Write-Host "   Intenta manualmente: cd flink-job && .\deploy-job.ps1" -ForegroundColor Gray
}

# Resumen final
$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✅ SISTEMA LEVANTADO EXITOSAMENTE                         ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "⏱️  Tiempo total: $([math]::Round($duration, 1)) segundos" -ForegroundColor Gray
Write-Host ""
Write-Host "🌐 URLs de acceso:" -ForegroundColor Cyan
Write-Host "   • Storage API:    http://localhost:5001/metrics" -ForegroundColor White
Write-Host "   • Kafka UI:       http://localhost:8080" -ForegroundColor White
Write-Host "   • Flink UI:       http://localhost:8081" -ForegroundColor White
Write-Host "   • Score API:      http://localhost:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "📊 Verificar estado:" -ForegroundColor Cyan
Write-Host "   docker ps --format 'table {{.Names}}\t{{.Status}}'" -ForegroundColor White
Write-Host ""
Write-Host "🔍 Ver logs:" -ForegroundColor Cyan
Write-Host "   docker logs -f flink_jobmanager    # Logs de Flink" -ForegroundColor White
Write-Host "   docker logs -f score_validator     # Logs de Score Validator" -ForegroundColor White
Write-Host "   docker logs -f storage_service     # Logs de Storage" -ForegroundColor White
Write-Host ""
Write-Host "📈 Monitoreo en tiempo real:" -ForegroundColor Cyan
Write-Host "   Start-Process 'http://localhost:8081'  # Flink Dashboard" -ForegroundColor White
Write-Host "   Start-Process 'http://localhost:8080'  # Kafka Topics" -ForegroundColor White
Write-Host ""
Write-Host "🛑 Para detener:" -ForegroundColor Cyan
Write-Host "   docker-compose -f docker-compose-tarea2.yml down" -ForegroundColor White
Write-Host ""
