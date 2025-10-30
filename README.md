# Sistema Asincrono de Procesamiento de Preguntas con Kafka

Sistema distribuido para procesar preguntas usando LLM (Large Language Model) con arquitectura asincrona basada en Kafka.

## Inicio Rapido

### 1. Requisitos

- Docker Desktop
- Ollama con modelo llama3.2
- Python 3.10+

### 2. Levantar el sistema

```bash
cd Docker/yahoo_llm_project
docker-compose up -d
```

### 3. Probar el sistema

```bash
# Enviar pregunta
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -d "{\"question_text\": \"Que es Docker?\", \"original_answer\": \"Contenedores\"}"

# Ver metricas
curl http://localhost:5001/metrics

# Kafka UI
# Abrir: http://localhost:8080
```

### 4. Ejecutar tests

```bash
python test_pipeline.py
python run_demo_cases.py
```

## Documentacion

- **GUIA_RAPIDA_EJECUCION.md** - Guia completa paso a paso
- **SISTEMA_COMPLETO_LISTO.md** - Documentacion tecnica detallada
- **CASOS_DEMO.md** - Casos de demostracion

## Arquitectura

```
Cliente -> Storage Service -> Kafka -> LLM Consumer -> Score Validator -> PostgreSQL + Redis
```

**11 servicios Docker:**
- Kafka + Zookeeper
- PostgreSQL + Redis
- Storage Service (API)
- LLM Consumer (x2)
- Retry Consumers (x2)
- Score Validator
- Kafka UI

**7 topics Kafka:**
- questions-pending
- llm-responses-success
- llm-responses-error-overload
- llm-responses-error-quota
- llm-responses-error-permanent
- validated-responses
- low-quality-responses

## Endpoints

- `POST /query` - Enviar pregunta (202 Accepted)
- `GET /status/{id}` - Consultar estado
- `GET /metrics` - Ver metricas del sistema

## Performance

- Latencia API: 8-25ms (respuesta inmediata)
- Procesamiento: 2-4 segundos (asincrono)
- Cache hit: 8ms (300x mas rapido)
- Throughput: 0.8 req/s
- Confiabilidad: 100% (con retries)

## Troubleshooting

Ver seccion completa en `GUIA_RAPIDA_EJECUCION.md`

Comandos basicos:
```bash
# Ver servicios
docker ps

# Ver logs
docker logs storage_service

# Reiniciar
docker-compose down
docker-compose up -d
```

## Autor

Fernanda Valencia
Nicolas Moreno
Sistemas Distribuidos - Tarea 2

## Licencia

Proyecto academico
