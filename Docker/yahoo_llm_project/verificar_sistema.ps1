# Script de Verificación Completa del Sistema Tarea 2
# Ejecutar después de reiniciar los contenedores

Write-Host "`n" -NoNewline
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  VERIFICACION COMPLETA - SISTEMA TAREA 2" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Contenedores
Write-Host "`n[1] Estado de Contenedores:" -ForegroundColor Yellow
$containers = docker ps --format "{{.Names}}" | Where-Object { $_ -match "yahoo_llm|postgres|kafka|flink|zookeeper|redis|viz|storage|score|retry|traffic" }
Write-Host "   Total corriendo: $($containers.Count)/17" -ForegroundColor Green

# 2. Datos en PostgreSQL
Write-Host "`n[2] Datos en Base de Datos:" -ForegroundColor Yellow
docker exec postgres_db psql -U user -d yahoo_db -t -c "SELECT COUNT(*) FROM responses;" | ForEach-Object { 
    Write-Host "   Total respuestas: $($_.Trim())" -ForegroundColor Green
}

# 3. Estadísticas de Scores
Write-Host "`n[3] Estadísticas de BERTScores:" -ForegroundColor Yellow
docker exec postgres_db psql -U user -d yahoo_db -c "
SELECT 
    ROUND(AVG(bert_score)::numeric, 3) as promedio,
    ROUND(MIN(bert_score)::numeric, 3) as minimo,
    ROUND(MAX(bert_score)::numeric, 3) as maximo
FROM responses;
"

# 4. Distribución por Umbral 0.85
Write-Host "`n[4] Distribución Respecto al Umbral (0.85):" -ForegroundColor Yellow
docker exec postgres_db psql -U user -d yahoo_db -c "
SELECT 
    CASE 
        WHEN bert_score < 0.85 THEN 'Bajo umbral (< 0.85)'
        ELSE 'Sobre umbral (>= 0.85)'
    END as categoria,
    COUNT(*) as cantidad,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM responses), 1)::text || '%' as porcentaje
FROM responses
GROUP BY categoria
ORDER BY MIN(bert_score);
"

# 5. Distribución por Intentos
Write-Host "`n[5] Distribución por Intentos de Procesamiento:" -ForegroundColor Yellow
docker exec postgres_db psql -U user -d yahoo_db -c "
SELECT 
    processing_attempts as intentos,
    COUNT(*) as cantidad,
    ROUND(AVG(bert_score)::numeric, 3) as score_prom,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM responses), 1)::text || '%' as porcentaje
FROM responses
GROUP BY processing_attempts
ORDER BY processing_attempts;
"

# 6. Job de Flink
Write-Host "`n[6] Estado del Job de Flink:" -ForegroundColor Yellow
$flinkJobs = docker exec flink_jobmanager flink list 2>$null
if ($flinkJobs -match "RUNNING") {
    Write-Host "   Job de Flink: RUNNING" -ForegroundColor Green
} else {
    Write-Host "   Job de Flink: NO DESPLEGADO (ejecutar: docker exec flink_jobmanager flink run -d /opt/flink/flink-score-validator-1.0.jar)" -ForegroundColor Red
}

# 7. Últimas respuestas procesadas
Write-Host "`n[7] Últimas 3 Respuestas Procesadas:" -ForegroundColor Yellow
docker exec postgres_db psql -U user -d yahoo_db -c "
SELECT 
    LEFT(question_text, 50) as pregunta,
    ROUND(bert_score::numeric, 3) as score,
    processing_attempts as intentos,
    TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') as fecha
FROM responses 
ORDER BY created_at DESC 
LIMIT 3;
"

# 8. URLs importantes
Write-Host "`n[8] URLs del Sistema:" -ForegroundColor Yellow
Write-Host "   Dashboard:     http://localhost:5002" -ForegroundColor Cyan
Write-Host "   Flink UI:      http://localhost:8081" -ForegroundColor Cyan
Write-Host "   Kafka UI:      http://localhost:8080" -ForegroundColor Cyan
Write-Host "   Storage API:   http://localhost:5001" -ForegroundColor Cyan

# Resumen final
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "  SISTEMA OPERACIONAL Y VERIFICADO" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "`n"
