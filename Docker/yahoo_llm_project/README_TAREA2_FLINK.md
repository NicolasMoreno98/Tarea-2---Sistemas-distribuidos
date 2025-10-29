# Sistema Yahoo LLM - Tarea 2 con Apache Flink

## 🎯 Descripción

Sistema completo de procesamiento asíncrono de consultas LLM con Apache Kafka y **Apache Flink**, implementando pipeline resiliente con reintentos, validación de calidad mediante BERTScore, y regeneración automática de respuestas de baja calidad.

## 🏗️ Arquitectura Completa

```
┌─────────────────┐
│  Storage API    │ ← HTTP POST /query
│  (Flask:5001)   │
└────────┬────────┘
         │ Produce
         ↓
┌─────────────────────────────────────────────────────────┐
│                   APACHE KAFKA                          │
│  Topics: questions-pending, llm-requests, errors-*,     │
│          llm-responses-success, validated-responses     │
└────┬──────────┬──────────────────────────────┬──────────┘
     │          │                               │
     ↓          ↓                               ↓
┌──────────┐ ┌──────────────┐         ┌──────────────────┐
│ LLM      │ │ Retry        │         │ FLINK CLUSTER    │
│ Consumer │ │ Consumers    │         │ ┌──────────────┐ │
│ (x2)     │ │ - Overload   │         │ │ JobManager   │ │
│          │ │ - Quota      │         │ │   :8081      │ │
└────┬─────┘ └──────┬───────┘         │ └──────┬───────┘ │
     │              │                  │        │         │
     │ Success      │ Retry            │ ┌──────▼───────┐ │
     ↓              ↓                  │ │ TaskManager  │ │
┌─────────────────────────────┐       │ └──────────────┘ │
│  llm-responses-success      │       │                  │
└──────────┬──────────────────┘       │ Score Validator  │
           │                          │ Job (Java)       │
           └─────────────────────────→│                  │
                                      └────┬──────┬──────┘
                                           │      │
                          Score < 0.75 ────┘      └──── Score ≥ 0.75
                                  │                         │
                                  ↓                         ↓
                         ┌────────────────┐       ┌────────────────┐
                         │ questions-     │       │ validated-     │
                         │ pending        │       │ responses      │
                         │ (regenerar)    │       │ (persistir)    │
                         └────────────────┘       └────────┬───────┘
                                                            │
                                                            ↓
                                                   ┌────────────────┐
                                                   │  PostgreSQL    │
                                                   │  + Redis Cache │
                                                   └────────────────┘
```

## 📦 Servicios (14 contenedores)

### Infraestructura Base (5)
1. **postgres_db** - PostgreSQL 13
2. **redis_cache** - Redis 7 con política LRU
3. **zookeeper** - Coordinación Kafka
4. **kafka_broker** - Broker Kafka
5. **kafka_init** - Inicializador de topics

### Aplicación (6)
6. **storage-service** - API REST (Flask:5001)
7. **llm-consumer-1** - Consumidor LLM (Ollama)
8. **llm-consumer-2** - Consumidor LLM (Ollama)
9. **retry-overload-consumer** - Reintentos 503
10. **retry-quota-consumer** - Reintentos 429
11. **score-validator** - HTTP API + Kafka Consumer

### Apache Flink (2)
12. **flink-jobmanager** - Coordinador Flink (:8081)
13. **flink-taskmanager** - Ejecutor de jobs

### Monitoreo (1)
14. **kafka-ui** - Interfaz gráfica Kafka (:8080)

## 🚀 Inicio Rápido

### Prerequisitos

- **Docker** y **Docker Compose**
- **Maven 3.6+** (para compilar Flink job)
- **Java 11+** (para Maven)
- **Ollama** corriendo localmente en puerto 11434 con modelo `tinyllama`

### Opción 1: Script Automatizado (Recomendado)

```powershell
cd "d:\U\Sistemas Distribuidos\Docker\yahoo_llm_project"
.\start-system.ps1
```

Este script:
1. ✅ Compila el Flink job con Maven
2. ✅ Detiene contenedores existentes
3. ✅ Levanta todos los servicios
4. ✅ Espera healthchecks
5. ✅ Despliega el Flink job automáticamente

**Tiempo estimado:** 3-4 minutos

### Opción 2: Manual

```powershell
# 1. Compilar Flink job
cd flink-job
mvn clean package -DskipTests
cd ..

# 2. Levantar servicios
docker-compose -f docker-compose-tarea2.yml up -d --build

# 3. Esperar 30 segundos para healthchecks
Start-Sleep -Seconds 30

# 4. Iniciar servicios manualmente (si Zookeeper se demora)
docker start kafka_broker
Start-Sleep -Seconds 15
docker start kafka_init storage_service yahoo_llm_project-llm-consumer-1 yahoo_llm_project-llm-consumer-2 retry_overload_consumer retry_quota_consumer score_validator kafka_ui traffic_generator
Start-Sleep -Seconds 10
docker start flink_jobmanager flink_taskmanager
Start-Sleep -Seconds 15

# 5. Desplegar Flink job
cd flink-job
.\deploy-job.ps1
```

## 🔍 Verificación del Sistema

### 1. Contenedores UP

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Deberías ver **14 contenedores** corriendo.

### 2. Storage API

```powershell
curl http://localhost:5001/metrics
```

Respuesta esperada:
```json
{
  "total_responses": 7887,
  "cache_hits": 0,
  "db_errors": 0
}
```

### 3. Flink Job Desplegado

Accede a http://localhost:8081

- Ve a **"Running Jobs"**
- Deberías ver: `Flink Score Validator Job`
- Estado: **RUNNING**

### 4. Kafka Topics

Accede a http://localhost:8080

Topics esperados:
- `questions-pending`
- `llm-requests`
- `llm-responses-success`
- `llm-responses-error`
- `errors-overload`
- `errors-quota`
- `validated-responses`
- `low-quality-responses`

### 5. Score Validator API

```powershell
curl http://localhost:8000/health
```

Respuesta:
```json
{
  "status": "healthy",
  "service": "score-validator"
}
```

## 🎮 Uso del Sistema

### Enviar pregunta

```powershell
curl -X POST http://localhost:5001/query `
  -H "Content-Type: application/json" `
  -d '{
    "question_text": "¿Cuál es la capital de Chile?",
    "original_answer": "La capital de Chile es Santiago"
  }'
```

### Flujo completo:

1. **Storage API** recibe pregunta → produce a `questions-pending`
2. **LLM Consumer** consume → llama Ollama → produce a `llm-responses-success` o `llm-responses-error`
3. **Flink Job** consume success → calcula BERTScore
   - **Score ≥ 0.75**: Produce a `validated-responses` → **se persiste**
   - **Score < 0.75**: Produce a `questions-pending` → **se regenera** (max 3 intentos)
4. **Score Validator** (Python) consume `llm-responses-success` en paralelo (backup)
5. Si hay errores 503/429: **Retry Consumers** reintentan con backoff

## 📊 Monitoreo

### Flink Dashboard
```powershell
Start-Process "http://localhost:8081"
```

Métricas disponibles:
- Jobs corriendo
- Throughput (mensajes/segundo)
- Latencia de procesamiento
- Checkpoints
- Backpressure

### Kafka UI
```powershell
Start-Process "http://localhost:8080"
```

Visualiza:
- Mensajes en cada topic
- Consumer groups
- Lag de consumidores
- Configuración de topics

### Logs en tiempo real

```powershell
# Flink
docker logs -f flink_jobmanager
docker logs -f flink_taskmanager

# Score Validator
docker logs -f score_validator

# LLM Consumers
docker logs -f yahoo_llm_project-llm-consumer-1

# Storage
docker logs -f storage_service

# Retry Consumers
docker logs -f retry_overload_consumer
docker logs -f retry_quota_consumer
```

## 🎯 Cumplimiento de Requerimientos

### ✅ Pipeline Asíncrono con Kafka
- 8 tópicos diseñados para gestión completa del ciclo de vida
- Productores: Storage API, LLM Consumer, Retry Consumers, Flink Job
- Consumidores: LLM Consumer (x2), Retry Consumers (x2), Flink Job, Score Validator

### ✅ Gestión de Fallos y Reintentos
- **Errores 503 (Overload)**: Exponential backoff (2^n * 5s)
- **Errores 429 (Quota)**: Fixed delay (60s)
- Consumidores dedicados por tipo de error
- Desacoplamiento total de la lógica de reintentos

### ✅ Procesamiento de Flujos con Flink
- **Job Java/Scala** en Flink 1.18
- Lee desde `llm-responses-success`
- Calcula BERTScore (vía HTTP API a score_validator)
- Decisión basada en umbral (0.75)
- Reinyección a `questions-pending` si score < 0.75
- Mecanismo anti-ciclos: máximo 3 reintentos

### ✅ Distribución y Despliegue
- **100% contenerizado** con Docker
- Orquestación con `docker-compose.yml` único
- Servicios escalables (LLM consumers con replicas: 2)
- Healthchecks configurados
- Volúmenes persistentes para datos

## 🛠️ Configuración Avanzada

### Cambiar umbral de calidad

**Flink Job** (`flink-job/src/main/java/.../ScoreValidatorJob.java`):
```java
private static final double QUALITY_THRESHOLD = 0.75;  // Cambiar aquí
```

Recompilar:
```powershell
cd flink-job
mvn clean package -DskipTests
docker exec flink_jobmanager flink cancel <job-id>
.\deploy-job.ps1
```

### Escalar LLM consumers

En `docker-compose-tarea2.yml`:
```yaml
llm-consumer:
  deploy:
    replicas: 4  # Aumentar de 2 a 4
```

### Cambiar estrategia de reintento

**Overload** (`retry_consumers/retry_overload_consumer.py`):
```python
delay = (2 ** retry_count) * 5  # Exponential backoff
```

**Quota** (`retry_consumers/retry_quota_consumer.py`):
```python
FIXED_DELAY_SECONDS = 60  # Cambiar delay
```

## 🧪 Testing

### Test básico de flujo completo

```powershell
# 1. Enviar pregunta
$response = curl -X POST http://localhost:5001/query `
  -H "Content-Type: application/json" `
  -d '{"question_text":"Test?","original_answer":"Test answer"}' `
  | ConvertFrom-Json

$questionId = $response.question_id

# 2. Esperar procesamiento
Start-Sleep -Seconds 10

# 3. Verificar en Kafka UI
Start-Process "http://localhost:8080/ui/clusters/local/all-topics/validated-responses"

# 4. Ver logs de Flink
docker logs flink_jobmanager | Select-String "FLINK: Validando"
```

### Test de regeneración (score bajo)

```powershell
# Enviar pregunta con respuesta muy diferente a la original
curl -X POST http://localhost:5001/query `
  -H "Content-Type: application/json" `
  -d '{
    "question_text": "¿Cuál es la capital de Francia?",
    "original_answer": "La capital de Francia es París"
  }'

# Observar logs de Flink
docker logs -f flink_jobmanager | Select-String "Regenerando pregunta"
```

## 📁 Estructura del Proyecto

```
Docker/yahoo_llm_project/
├── docker-compose-tarea2.yml       # Orquestación (14 servicios)
├── start-system.ps1                # Script de inicio automático
├── flink-job/                      # Apache Flink Job
│   ├── pom.xml                     # Maven config
│   ├── Dockerfile                  # Build multi-stage
│   ├── deploy-job.ps1              # Deploy script
│   ├── README.md                   # Docs del job
│   └── src/main/java/.../          # Código Java
│       └── ScoreValidatorJob.java  # Job principal
├── llm_consumer/                   # Consumidor LLM
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── retry_consumers/                # Consumidores de reintentos
│   ├── Dockerfile.overload
│   ├── Dockerfile.quota
│   ├── retry_overload_consumer.py
│   ├── retry_quota_consumer.py
│   └── requirements.txt
├── score_validator/                # API + Consumer Python
│   ├── Dockerfile
│   ├── app.py                      # Flask API + Kafka consumer
│   └── requirements.txt            # Incluye flask
├── storage_service/                # API REST principal
├── traffic_generator/              # Generador de carga
├── postgres/                       # Schemas SQL
└── redis/                          # Configuración Redis
```

## 🔧 Troubleshooting

### Problema: Flink job no se despliega

```powershell
# Verificar que JobManager esté healthy
docker ps | Select-String flink

# Ver logs
docker logs flink_jobmanager

# Reintentar despliegue manual
cd flink-job
.\deploy-job.ps1
```

### Problema: Maven no compila

```powershell
# Verificar Java
java -version  # Debe ser 11+

# Limpiar cache Maven
cd flink-job
mvn clean
Remove-Item -Recurse -Force ~/.m2/repository/com/yahoo
mvn package -DskipTests
```

### Problema: Zookeeper timeout

Este es un problema conocido. Solución:

```powershell
# Esperar 30 segundos y luego iniciar manualmente
Start-Sleep -Seconds 30
docker start kafka_broker
# ... resto de servicios
```

### Problema: Score Validator no responde HTTP

```powershell
# Verificar puerto expuesto
docker ps | Select-String score_validator

# Ver logs
docker logs score_validator | Select-String "Iniciando HTTP"

# Test directo
curl http://localhost:8000/health
```

## 📚 Referencias

- **Apache Flink:** https://flink.apache.org/
- **Flink Kafka Connector:** https://nightlies.apache.org/flink/flink-docs-master/docs/connectors/datastream/kafka/
- **BERTScore:** https://github.com/Tiiiger/bert_score
- **Kafka:** https://kafka.apache.org/

## 🎓 Decisiones de Diseño

### ¿Por qué Flink + Score Validator?

- **Flink**: Procesamiento de streams en tiempo real, decisiones de regeneración
- **Score Validator**: API HTTP para cálculos de BERTScore, backup Kafka consumer
- **Ambos trabajan en paralelo**: Redundancia y flexibilidad

### ¿Por qué HTTP API en score_validator?

- Flink necesita calcular BERTScore sin reimplementar en Java
- score_validator ya tiene el modelo cargado (PyTorch + Transformers)
- HTTP API permite reutilización del código Python existente

### ¿Por qué 2 LLM consumers?

- Escalabilidad: Procesar más mensajes en paralelo
- Resiliencia: Si uno falla, el otro sigue funcionando
- Load balancing: Kafka distribuye mensajes automáticamente

## 📄 Licencia

Proyecto académico - Sistemas Distribuidos - 2025
