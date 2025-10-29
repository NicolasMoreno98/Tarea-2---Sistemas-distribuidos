# Script para ver todas las estadisticas del experimento

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "ESTADISTICAS DEL EXPERIMENTO" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# 1. Logs del Traffic Generator
Write-Host "[1] LOGS DEL TRAFFIC GENERATOR:" -ForegroundColor Green
Write-Host "----------------------------------------`n" -ForegroundColor Gray
docker logs traffic-generator --tail 50

# 2. Estado de contenedores
Write-Host "`n`n[2] ESTADO DE CONTENEDORES:" -ForegroundColor Green
Write-Host "----------------------------------------`n" -ForegroundColor Gray
docker-compose -f ../docker-compose-tarea2.yml ps

# 3. Estadisticas de Kafka
Write-Host "`n`n[3] ESTADISTICAS DE KAFKA:" -ForegroundColor Green
Write-Host "----------------------------------------`n" -ForegroundColor Gray
python monitor_kafka_statistics.py once

# 4. Base de datos - respuestas recientes
Write-Host "`n`n[4] RESPUESTAS RECIENTES (ultimos 10 min):" -ForegroundColor Green
Write-Host "----------------------------------------`n" -ForegroundColor Gray
docker exec postgres_db psql -U user -d yahoo_db -c "SELECT COUNT(*) as respuestas_recientes, MIN(created_at) as primera, MAX(created_at) as ultima FROM responses WHERE created_at >= NOW() - INTERVAL '10 minutes';"

# 5. Estadisticas totales de BD
Write-Host "`n`n[5] ESTADISTICAS TOTALES DE BASE DE DATOS:" -ForegroundColor Green
Write-Host "----------------------------------------`n" -ForegroundColor Gray
docker exec postgres_db psql -U user -d yahoo_db -c "SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE bert_score >= 0.80) as aprobadas, COUNT(*) FILTER (WHERE bert_score < 0.80) as rechazadas, ROUND(AVG(bert_score)::numeric, 4) as score_promedio FROM responses;"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "FIN DEL REPORTE" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
