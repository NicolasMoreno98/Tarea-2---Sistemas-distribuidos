@echo off
REM Guía de inicio rápido para Yahoo LLM System - Windows

echo Yahoo LLM Evaluation System - Guía de Inicio Rápido
echo ======================================================

echo.
echo PASOS A SEGUIR:
echo.

echo 1. Verificar Ollama está instalado y funcionando:
echo    ollama list
echo.

echo 2. Si no tienes TinyLlama, descargarlo (recomendado para velocidad):
echo    ollama pull tinyllama:latest
echo.

echo 3. [OPCIONAL] Cambiar número de consultas:
echo    - Abrir: traffic_generator\generator.py
echo    - Modificar línea 14: NUM_REQUESTS = 10
echo    - Guardar archivo
echo.

echo 4. Levantar el sistema:
echo    docker-compose up -d
echo.

echo 5. Verificar que todos los servicios están corriendo:
echo    docker ps
echo.

echo 6. Probar conectividad (PowerShell):
echo    Invoke-WebRequest -Uri http://localhost:5000/health -Method GET
echo.

echo 7. Ejecutar el experimento:
echo    docker exec -it yahoo_llm_project-traffic-generator-1 python /app/generator.py
echo.

echo 8. Ver resultados en base de datos:
echo    docker exec -it yahoo_llm_project-postgres-1 psql -U user -d yahoo_db -c "SELECT COUNT(*) FROM responses;"
echo.

echo 9. Apagar sistema cuando termines:
echo    docker-compose down
echo.

echo UBICACIÓN DE RESULTADOS:
echo    - Base de datos: PostgreSQL (puerto 5432)
echo    - Archivo JSON: dataset\response.json
echo    - Cache: Redis (puerto 6379)
echo.

echo CONFIGURACIONES RÁPIDAS:
echo    - Demo (15s): NUM_REQUESTS = 5
echo    - Evaluación (2min): NUM_REQUESTS = 50
echo    - Completo (3h): NUM_REQUESTS = 10000
echo.

echo Para más detalles, ver README.md
echo.

pause