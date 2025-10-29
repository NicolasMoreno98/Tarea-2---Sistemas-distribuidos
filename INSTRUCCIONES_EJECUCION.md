# Guia de Ejecucion - Tarea 2

## Prerequisitos

1. Docker Desktop instalado y ejecutandose
2. Ollama ejecutandose en localhost:11434 con modelo llama3.2
3. Python 3.11+ (para scripts de prueba)

## Paso 1: Preparar el entorno

```powershell
# Navegar al directorio del proyecto
cd "d:\U\Sistemas Distribuidos\Docker\yahoo_llm_project"

# Verificar que Ollama esta corriendo
curl http://localhost:11434/api/tags
```

## Paso 2: Levantar infraestructura

```powershell
# Levantar servicios base (Kafka, Zookeeper, PostgreSQL, Redis)
docker-compose -f docker-compose-tarea2.yml up -d zookeeper kafka postgres redis

# Esperar 30 segundos para que se inicialicen
Start-Sleep -Seconds 30

# Verificar que los servicios estan corriendo
docker-compose -f docker-compose-tarea2.yml ps
```

## Paso 3: Crear topicos de Kafka

```powershell
# Ejecutar servicio de inicializacion de topicos
docker-compose -f docker-compose-tarea2.yml up kafka-init

# Verificar topicos creados
docker exec kafka_broker kafka-topics --bootstrap-server localhost:9092 --list
```

Topicos esperados:
- questions-pending
- llm-responses-success
- llm-responses-error-overload
- llm-responses-error-quota
- llm-responses-error-permanent
- validated-responses
- low-quality-responses

## Paso 4: Levantar servicios de procesamiento

```powershell
# Levantar Storage Service
docker-compose -f docker-compose-tarea2.yml up -d storage-service

# Levantar LLM Consumer (2 replicas)
docker-compose -f docker-compose-tarea2.yml up -d --scale llm-consumer=2 llm-consumer

# Levantar Retry Consumers
docker-compose -f docker-compose-tarea2.yml up -d retry-overload-consumer retry-quota-consumer

# Levantar Score Validator
docker-compose -f docker-compose-tarea2.yml up -d score-validator

# Levantar Kafka UI (opcional, para monitoreo)
docker-compose -f docker-compose-tarea2.yml up -d kafka-ui
```

## Paso 5: Verificar servicios

```powershell
# Ver logs del LLM Consumer
docker logs llm_consumer_1 -f

# Ver logs del Storage Service
docker logs storage_service -f

# Acceder a Kafka UI
# Abrir navegador en: http://localhost:8080
```

## Paso 6: Ejecutar pruebas

```powershell
# Volver al directorio raiz
cd "d:\U\Sistemas Distribuidos"

# Instalar dependencias de prueba
pip install requests

# Ejecutar script de prueba
python test_pipeline.py
```

## Paso 7: Monitoreo en tiempo real

### Opcion A: Kafka UI (Recomendado)
1. Abrir http://localhost:8080
2. Navegar a Topics
3. Ver mensajes en tiempo real

### Opcion B: Logs de Docker
```powershell
# Ver logs de todos los servicios
docker-compose -f docker-compose-tarea2.yml logs -f

# Ver logs especificos
docker logs llm_consumer_1 -f
docker logs score_validator -f
docker logs retry_overload_consumer -f
```

## Paso 8: Consultas de ejemplo

### Enviar pregunta nueva
```powershell
curl -X POST http://localhost:5001/query `
  -H "Content-Type: application/json" `
  -d '{"question": "Qu es Kubernetes?", "context": "Orquestacion de contenedores"}'
```

### Consultar estado de pregunta
```powershell
# Reemplazar QUESTION_ID con el ID retornado
curl http://localhost:5001/status/QUESTION_ID
```

### Consultar metricas
```powershell
curl http://localhost:5001/metrics
```

## Casos de Prueba Especificos

### Caso 1: Flujo Normal
- Pregunta: "Qu es Docker?"
- Esperado: 202 Accepted  LLM procesa  Score validator aprueba  200 OK

### Caso 2: Error Overload (Simulado)
```powershell
# Detener Ollama temporalmente
# Enviar pregunta
# Ver retry con exponential backoff en logs
# Reiniciar Ollama
# Ver exito en reintento
```

### Caso 3: Regeneracion por Score Bajo
- Modificar temporalmente umbral en score_validator
- Enviar pregunta
- Ver reintento automatico

### Caso 4: Cache Hit
- Enviar misma pregunta dos veces
- Segunda vez debe retornar 200 OK inmediatamente

## Detencion del Sistema

```powershell
# Detener todos los servicios
docker-compose -f docker-compose-tarea2.yml down

# Limpiar volumenes (CUIDADO: borra datos)
docker-compose -f docker-compose-tarea2.yml down -v
```

## Troubleshooting

### Kafka no se conecta
```powershell
# Reiniciar Kafka
docker-compose -f docker-compose-tarea2.yml restart kafka

# Ver logs
docker logs kafka_broker
```

### LLM Consumer no procesa
```powershell
# Verificar Ollama
curl http://localhost:11434/api/tags

# Ver logs del consumer
docker logs llm_consumer_1

# Verificar topico
docker exec kafka_broker kafka-console-consumer --bootstrap-server localhost:9092 --topic questions-pending --from-beginning
```

### Storage Service no responde
```powershell
# Verificar health
curl http://localhost:5001/health

# Ver logs
docker logs storage_service

# Verificar PostgreSQL
docker exec postgres_db psql -U user -d yahoo_db -c "SELECT COUNT(*) FROM responses;"
```

## Estructura de Directorios Esperada

```
d:\U\Sistemas Distribuidos\
 Docker\
    yahoo_llm_project\
        docker-compose-tarea2.yml
        ...
 llm_consumer\
    app.py
    Dockerfile
    requirements.txt
 retry_consumers\
    retry_overload_consumer.py
    retry_quota_consumer.py
    Dockerfile.overload
    Dockerfile.quota
    requirements.txt
 score_validator\
    app.py
    Dockerfile
    requirements.txt
 storage_service\
    ...
 test_pipeline.py
 migrate_tarea1_data.py
```

## Comandos Utiles

```powershell
# Ver todos los contenedores
docker ps -a

# Ver uso de recursos
docker stats

# Acceder a shell de PostgreSQL
docker exec -it postgres_db psql -U user -d yahoo_db

# Consumir mensajes de Kafka
docker exec kafka_broker kafka-console-consumer --bootstrap-server localhost:9092 --topic validated-responses --from-beginning

# Ver grupos de consumidores
docker exec kafka_broker kafka-consumer-groups --bootstrap-server localhost:9092 --list
```
