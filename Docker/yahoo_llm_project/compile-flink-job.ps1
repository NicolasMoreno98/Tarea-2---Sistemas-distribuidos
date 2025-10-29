# Script para compilar Flink Job usando Docker (sin necesidad de Maven local)

Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "  Compilando Flink Job usando contenedor Maven              " -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Compilando con Maven en Docker..." -ForegroundColor Yellow

# Compilar usando contenedor Maven oficial
docker run --rm `
    -v "$PSScriptRoot\flink-job:/app" `
    -w /app `
    maven:3.9-eclipse-temurin-11 `
    mvn clean package -DskipTests

if ($LASTEXITCODE -eq 0) {
    Write-Host "Compilacion exitosa" -ForegroundColor Green
    Write-Host "JAR generado: flink-job/target/flink-score-validator-1.0.jar" -ForegroundColor Yellow
    
    # Verificar que el JAR existe
    if (Test-Path "$PSScriptRoot\flink-job\target\flink-score-validator-1.0.jar") {
        $jarSize = (Get-Item "$PSScriptRoot\flink-job\target\flink-score-validator-1.0.jar").Length / 1MB
        Write-Host "   Tamaño: $([math]::Round($jarSize, 2)) MB" -ForegroundColor Gray
    }
} else {
    Write-Host "Error en la compilacion" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Siguiente paso: Ejecutar .\start-system.ps1 para levantar todo el sistema" -ForegroundColor Cyan
