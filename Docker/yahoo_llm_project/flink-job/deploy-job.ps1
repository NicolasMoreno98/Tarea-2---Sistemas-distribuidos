# Script PowerShell para compilar y desplegar el Flink job

Write-Host "🔨 Compilando Flink job con Maven..." -ForegroundColor Cyan

# Compilar el proyecto
Push-Location $PSScriptRoot
$compileResult = & mvn clean package -DskipTests 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al compilar el proyecto" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "✅ Compilación exitosa" -ForegroundColor Green
Write-Host "📦 JAR generado: target/flink-score-validator-1.0.jar" -ForegroundColor Yellow

# Esperar a que Flink JobManager esté listo
Write-Host "⏳ Esperando a que Flink JobManager esté disponible..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

# Desplegar el job en Flink
Write-Host "🚀 Desplegando job en Flink..." -ForegroundColor Cyan
$deployResult = docker exec flink_jobmanager flink run -d /opt/flink-job/target/flink-score-validator-1.0.jar 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Job desplegado exitosamente" -ForegroundColor Green
    Write-Host "🌐 Accede a Flink UI en: http://localhost:8081" -ForegroundColor Yellow
} else {
    Write-Host "❌ Error al desplegar el job" -ForegroundColor Red
    Write-Host $deployResult
    Pop-Location
    exit 1
}

Pop-Location
