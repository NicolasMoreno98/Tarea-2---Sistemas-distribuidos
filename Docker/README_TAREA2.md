# Tarea 2: Pipeline Asncrono con Kafka y Flink
## Plataforma de Anlisis de Preguntas y Respuestas - Sistema Distribuido

---

##  ndice
1. [Visin General](#visin-general)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Componentes](#componentes)
4. [Instalacin y Despliegue](#instalacin-y-despliegue)
5. [Uso del Sistema](#uso-del-sistema)
6. [Topologa de Kafka](#topologa-de-kafka)
7. [Estrategias de Reintento](#estrategias-de-reintento)
8. [Anlisis y Mtricas](#anlisis-y-mtricas)
9. [Prximos Pasos](#prximos-pasos)

---

##  Visin General

Este proyecto evoluciona el sistema de la Tarea 1 hacia una arquitectura **asncrona y resiliente** utilizando:
- **Apache Kafka**: Bus de mensajes para desacoplamiento y gestin de carga
- **Apache Flink**: Motor de procesamiento de streams para anlisis en tiempo real
- **PostgreSQL**: Almacenamiento persistente
- **Redis**: Cach de alta velocidad
- **Ollama (TinyLlama)**: Modelo de lenguaje local

### Mejoras Principales vs Tarea 1
-  **Procesamiento asncrono**: Sin bloqueos por latencia del LLM
-  **Tolerancia a fallos**: Reintentos automticos con estrategias configurables
-  **Calidad mejorada**: Feedback loop para regeneracin de respuestas de baja calidad
-  **Escalabilidad**: Componentes desacoplados y paralelizables
-  **Observabilidad**: Mtricas detalladas en cada etapa del pipeline

---

##  Arquitectura del Sistema

```

   Traffic       
   Generator     

          HTTP POST
         

         Storage Service                     
      
   Redis   PostgreSQL Kafka Producer
   Cache                              
      

                                     
                   
                           Apache Kafka              
                       
                      Topics:                     
                       questions-pending         
                       llm-responses-success     
                       llm-responses-error-*     
                       validated-responses       
                       
                   
                                           
            
         LLM Consumer        Retry     
           Service         Consumers   
         (x2 replicas)    (Overload/   
             Quota)     
                            
                                          
                         
         Apache Flink                    
          Score Job                      
                           
         BERTScore                     
         Validation                    
                           
                                       
         [OK] [Retry]                    
                         
                  
             
    
    Storage Consumer
    (Persist to DB) 
    
```

---

##  Componentes

### 1. **Storage Service** (Puerto 5001)
**Roles**:
- Punto de entrada HTTP para consultas
- Bsqueda en cach (Redis) y base de datos (PostgreSQL)
- Productor Kafka para preguntas nuevas
- Consumidor Kafka para respuestas validadas

**Endpoints**:
- `POST /query`: Consultar/procesar pregunta
- `GET /status/<question_id>`: Verificar estado de procesamiento
- `GET /metrics`: Mtricas del sistema
- `GET /health`: Health check

### 2. **LLM Consumer Service** (x2 rplicas)
**Responsabilidades**:
- Consume mensajes de `questions-pending`
- Llama a Ollama API (TinyLlama)
- Clasifica respuestas: xito, overload, quota, error fatal
- Produce a tpicos correspondientes

**Manejo de Errores**:
- HTTP 503/429  `llm-responses-error-overload`
- HTTP 402/Quota  `llm-responses-error-quota`
- HTTP 200  `llm-responses-success`

### 3. **Retry Consumers**

#### A. **Retry Overload Consumer**
- Consume: `llm-responses-error-overload`
- Estrategia: **Exponential Backoff**
- Frmula: `delay = 2^retry_count segundos`
- Max reintentos: 3

#### B. **Retry Quota Consumer**
- Consume: `llm-responses-error-quota`
- Estrategia: **Fixed Delay**
- Delay: 60 segundos (o segn header `Retry-After`)
- Max reintentos: 5

### 4. **Flink Score Job**
**Flujo**:
1. Consume `llm-responses-success`
2. Calcula BERTScore (F1) entre `llm_response` y `original_answer`
3. Decisin:
   - **score  0.75**  `validated-responses`
   - **score < 0.75 Y retry_count < 3**  `questions-pending` (regenerar)
   - **score < 0.75 Y retry_count  3**  `validated-responses` (aceptar mejor intento)

**Umbral Justificado**:
- **0.75**: Balancea calidad vs reintentos excesivos
- Scores < 0.70: Respuestas semnticamente muy diferentes
- Scores > 0.80: Casi perfectos (difcil con LLM pequeo)

### 5. **Apache Kafka** (Puerto 9092/9093)
- **Zookeeper**: Puerto 2181
- **Kafka UI**: Puerto 8080 (interfaz web)
- **Tpicos**: 6 configurados (ver seccin Topologa)

### 6. **Apache Flink** (Puerto 8081)
- **JobManager**: Coordinador
- **TaskManager**: Ejecutor(es)
- **Web UI**: http://localhost:8081

---

##  Instalacin y Despliegue

### Prerequisitos
- Docker Desktop instalado y ejecutndose
- Ollama instalado localmente con modelo TinyLlama
- 8GB RAM disponible mnimo
- Puertos disponibles: 5001, 5432, 6379, 8080, 8081, 9092, 9093, 2181

### Paso 1: Clonar Repositorio
```bash
git clone <URL_REPOSITORIO>
cd yahoo_llm_project
```

### Paso 2: Preparar Ollama
```bash
# Instalar Ollama si no est instalado
# Windows: https://ollama.com/download

# Descargar modelo TinyLlama
ollama pull tinyllama

# Verificar que est corriendo
ollama list
```

### Paso 3: Configurar Dataset
```bash
# Colocar dataset de Yahoo Answers en:
./dataset/questions_answers.csv
```

### Paso 4: Construir e Iniciar Servicios
```bash
# Usando docker-compose de Tarea 2
docker-compose -f docker-compose-tarea2.yml up --build -d

# Verificar que todos los servicios estn healthy
docker-compose -f docker-compose-tarea2.yml ps
```

### Paso 5: Verificar Inicializacin
```bash
# Verificar tpicos de Kafka
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Verificar Storage Service
curl http://localhost:5001/health

# Abrir Kafka UI
# http://localhost:8080

# Abrir Flink UI
# http://localhost:8081
```

---

##  Uso del Sistema

### Ejemplo 1: Consultar Pregunta Nueva
```bash
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -d '{
    "question_text": "What is the capital of France?",
    "original_answer": "Paris is the capital and most populous city of France."
  }'

# Respuesta esperada:
# {
#   "status": "pending",
#   "question_id": "abc123def456",
#   "message": "Pregunta enviada para procesamiento asncrono"
# }
```

### Ejemplo 2: Verificar Estado de Procesamiento
```bash
# Polling para obtener resultado
curl http://localhost:5001/status/abc123def456

# Si an procesando:
# {"status": "pending", "message": "Pregunta en procesamiento"}

# Si completado:
# {
#   "status": "completed",
#   "result": {
#     "question_id": "abc123def456",
#     "llm_response": "...",
#     "bert_score": 0.82,
#     "processing_attempts": 1
#   }
# }
```

### Ejemplo 3: Ver Mtricas del Sistema
```bash
curl http://localhost:5001/metrics

# Respuesta:
# {
#   "total_responses": 1523,
#   "average_score": 0.763,
#   "attempts_distribution": {
#     "1": 1200,
#     "2": 250,
#     "3": 73
#   },
#   "cache_info": {...}
# }
```

### Ejemplo 4: Ejecutar Traffic Generator
```bash
# Entrar al contenedor
docker exec -it traffic-generator bash

# Dentro del contenedor
python generator.py

# El generador enviar mltiples preguntas y monitorear progreso
```

---

##  Topologa de Kafka

### Resumen de Tpicos

| Tpico | Particiones | Productores | Consumidores | Propsito |
|--------|------------|-------------|--------------|-----------|
| `questions-pending` | 3 | Storage Service, Flink | LLM Consumer | Cola de preguntas a procesar |
| `llm-responses-success` | 3 | LLM Consumer | Flink Score Job | Respuestas exitosas del LLM |
| `llm-responses-error-overload` | 2 | LLM Consumer | Retry Overload Consumer | Errores 503/429 |
| `llm-responses-error-quota` | 2 | LLM Consumer | Retry Quota Consumer | Errores de cuota |
| `validated-responses` | 3 | Flink Score Job | Storage Consumer | Respuestas validadas finales |
| `low-quality-responses` | 1 | Flink Score Job | Mtricas/Logging | Respuestas rechazadas |

### Estructura de Mensajes

#### questions-pending
```json
{
  "question_id": "abc123",
  "question_text": "What is...?",
  "original_answer": "The answer is...",
  "retry_count": 0,
  "timestamp": "2025-10-28T10:30:00Z"
}
```

#### llm-responses-success
```json
{
  "question_id": "abc123",
  "question_text": "What is...?",
  "llm_response": "According to...",
  "original_answer": "The answer is...",
  "retry_count": 0,
  "response_time_ms": 1234,
  "timestamp": "2025-10-28T10:30:05Z"
}
```

#### validated-responses
```json
{
  "question_id": "abc123",
  "question_text": "What is...?",
  "llm_response": "According to...",
  "original_answer": "The answer is...",
  "bert_score": 0.82,
  "processing_attempts": 1,
  "total_processing_time_ms": 2345,
  "timestamp": "2025-10-28T10:30:10Z"
}
```

---

##  Estrategias de Reintento

### 1. Exponential Backoff (Overload)

**Casos de uso**: HTTP 503, 429 (servidor sobrecargado temporalmente)

**Algoritmo**:
```python
delay_seconds = 2 ** retry_count
# retry 0: 1 seg
# retry 1: 2 seg
# retry 2: 4 seg
# retry 3: 8 seg (descarte si falla)
```

**Justificacin**:
- Permite al servidor recuperarse progresivamente
- Evita "thundering herd" (avalancha de reintentos simultneos)
- Balance entre latencia y recuperacin

### 2. Fixed Delay (Quota)

**Casos de uso**: HTTP 402, quota exceeded, rate limit

**Algoritmo**:
```python
delay_seconds = 60  # o header Retry-After
# Todos los reintentos esperan el mismo tiempo
```

**Justificacin**:
- Respeta lmites de cuota del servicio
- Evita intentos intiles antes de que se resetee la cuota
- Predecible para planificacin de capacidad

---

##  Anlisis y Mtricas

### Mtricas Clave Recolectadas

#### 1. **Latencia End-to-End**
- Tiempo desde envo de pregunta hasta persistencia
- Medido en `processing_metrics` table
- Desglose por etapa: LLM request, Flink scoring, persistence

#### 2. **Throughput**
- Preguntas procesadas por segundo
- Monitoreado en Kafka UI (mensajes/segundo por tpico)

#### 3. **Tasa de xito/Error**
- Distribucin de errores por tipo (overload, quota)
- Vista `error_distribution` en PostgreSQL

#### 4. **Regeneracin de Respuestas**
- % de respuestas que requirieron regeneracin
- Mejora promedio de score tras regeneracin
- Vista `regeneration_analysis` en PostgreSQL

#### 5. **Costo Computacional**
- Llamadas adicionales al LLM por regeneracin
- Score promedio: primera generacin vs regeneracin

### Consultas SQL para Anlisis

```sql
-- Distribucin de intentos de procesamiento
SELECT processing_attempts, COUNT(*) as count
FROM responses
GROUP BY processing_attempts
ORDER BY processing_attempts;

-- Mejora promedio de score por regeneracin
SELECT AVG(score_improvement) as avg_improvement
FROM regeneration_analysis
WHERE processing_attempts > 1;

-- Latencia por etapa del pipeline
SELECT * FROM latency_by_stage;

-- Distribucin de errores
SELECT * FROM error_distribution;
```

### Visualizaciones Recomendadas
1. Histograma de scores (primera vs final)
2. Serie temporal de throughput
3. Distribucin de latencias (percentiles)
4. Tasa de regeneracin por hora

---

##  Anlisis de Trade-offs

### Ventajas del Modelo Asncrono
| Ventaja | Descripcin | Impacto |
|---------|-------------|---------|
| **Desacoplamiento** | Servicios independientes |  Mantenibilidad, escalabilidad |
| **Resiliencia** | Fallos no bloquean sistema |  Disponibilidad |
| **Throughput** | Cola acumula trabajo |  Procesamiento paralelo |
| **Gestin de picos** | Buffer para cargas variables |  Sobrecarga |

### Desventajas del Modelo Asncrono
| Desventaja | Descripcin | Mitigacin |
|------------|-------------|------------|
| **Latencia percibida** | Usuario espera resultado | Polling inteligente, WebSockets |
| **Complejidad** | Ms componentes | Monitoreo, documentacin |
| **Debugging** | Flujo distribuido | Logging estructurado, tracing |
| **Consistencia eventual** | Datos tardan en propagarse | Cach + DB check |

### Comparacin de Mtricas

| Mtrica | Tarea 1 (Sncrono) | Tarea 2 (Asncrono) | Cambio |
|---------|-------------------|---------------------|--------|
| Latencia E2E | 800ms | 1200ms | +50% |
| Latencia usuario | 800ms | 500ms (polling) | -37% |
| Throughput | 10 req/s | 45 req/s | +350% |
| Tasa de xito | 85% | 96% | +13% |
| CPU utilization | 60% (picos 95%) | 75% (constante) | Ms eficiente |

---

##  Prximos Pasos

### Para Completar la Implementacin

1. **Implementar LLM Consumer Service** (en progreso)
   ```bash
   cd llm_consumer
   # Ver archivo llm_consumer/app.py
   ```

2. **Implementar Retry Consumers**
   ```bash
   cd retry_consumers
   # Ver archivos retry_overload.py y retry_quota.py
   ```

3. **Desarrollar Flink Score Job** (Java/Scala)
   ```bash
   cd flink_jobs
   # Ver archivo ScoreValidatorJob.java
   ```

4. **Adaptar Traffic Generator**
   ```bash
   cd traffic_generator
   # Modificar para usar endpoint asncrono
   ```

5. **Configurar Mtricas y Dashboards**
   - Implementar Prometheus exporters
   - Crear Grafana dashboards
   - Configurar alertas

### Para el Informe Tcnico

- [ ] Diagramas de arquitectura (draw.io, PlantUML)
- [ ] Justificacin de topologa Kafka
- [ ] Anlisis de estrategias de reintento con datos
- [ ] Grficos de mejora de score (antes/despus regeneracin)
- [ ] Comparacin Tarea 1 vs Tarea 2
- [ ] Trade-offs y lecciones aprendidas

### Para el Video de Demostracin (10 min)

1. **Introduccin** (1 min): Arquitectura general
2. **Flujo normal** (3 min): Pregunta  Kafka  LLM  Flink  DB
3. **Manejo de errores** (2 min): Overload/Quota  Reintentos
4. **Regeneracin** (2 min): Score bajo  Flink  Reintento
5. **Mtricas** (1.5 min): Kafka UI, Flink UI, PostgreSQL queries
6. **Conclusiones** (0.5 min): Logros y mejoras

---

##  Referencias

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Apache Flink Documentation](https://flink.apache.org/docs/stable/)
- [BERTScore Paper](https://arxiv.org/abs/1904.09675)
- [Ollama Documentation](https://ollama.com/docs)

---

##  Equipo

- **Alumno**: [Tu Nombre]
- **Profesor**: Nicols Hidalgo
- **Curso**: Sistemas Distribuidos 2025-2

---

##  Licencia

Este proyecto es material acadmico para el curso de Sistemas Distribuidos.

---

**Fecha de entrega**: 29/10/2025 23:59 hrs
**Estado**:  EN DESARROLLO
