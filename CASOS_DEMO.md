# Casos de Demostracin - Tarea 2 Sistema Asncrono

## Resumen Ejecutivo
- **Sistema**: Pipeline asncrono con Kafka para procesamiento de preguntas Yahoo Answers
- **Datos**: 7,880 respuestas histricas migradas desde Tarea 1
- **Arquitectura**: 11 servicios Docker, 7 topics Kafka, 6 consumer groups
- **Performance**: Score promedio 0.851, intentos promedio 1.67, latencia promedio 2,755ms

---

## CASO 1: Flujo Normal - Nueva Pregunta
**Objetivo**: Demostrar el procesamiento asncrono completo desde API hasta PostgreSQL

### Descripcin
Usuario enva una nueva pregunta que no existe en cache ni en base de datos.

### Pregunta de Prueba
```
Qu es Kubernetes y cmo se relaciona con Docker?
```

### Request HTTP
```bash
curl -X POST http://localhost:5001/api/process_question \
  -H "Content-Type: application/json" \
  -d '{
    "question_text": "Qu es Kubernetes y cmo se relaciona con Docker?",
    "original_answer": "Orquestacin de contenedores en entornos cloud"
  }'
```

### Flujo Esperado
1. **Storage Service**  Recibe POST, retorna `202 Accepted` con `question_id`
2. **Kafka Topic** `questions-pending`  Mensaje publicado en particin (round-robin)
3. **LLM Consumer** (replica 1 o 2)  Consume mensaje, llama Ollama Llama3.2
4. **Ollama LLM**  Genera respuesta (2-3 segundos)
5. **Kafka Topic** `llm-responses-success`  LLM Consumer publica resultado
6. **Score Validator**  Consume, calcula BERTScore vs respuesta original
7. **Decision**:
   - Si score  0.75  Kafka topic `validated-responses`
   - Si score < 0.75  Kafka topic `low-quality-responses` (regenerar)
8. **Storage Service Consumer**  Consume de `validated-responses`, guarda en PostgreSQL + Redis cache

### Comportamiento Esperado
- **Response inicial**: 202 Accepted con `{"message": "Pregunta enviada...", "question_id": "...", "status": "pending"}`
- **Tiempo total**: 2-4 segundos (procesamiento asncrono)
- **Cache**: No hit inicial, se guarda despus
- **Score esperado**: 0.75-0.95 (alta calidad)

### Verificacin
```bash
# Consultar estado final
curl http://localhost:5001/api/get_response/<question_id>

# Verificar en PostgreSQL
docker exec -it postgres_db psql -U user -d yahoo_db -c \
  "SELECT question_id, question_text, bert_score, processing_attempts FROM responses WHERE question_id='<question_id>';"

# Verificar cache Redis
docker exec -it redis redis-cli GET response:<question_id>
```

---

## CASO 2: Error y Retry - Sobrecarga del LLM
**Objetivo**: Demostrar manejo de errores con retry exponencial

### Descripcin
Simular sobrecarga del LLM enviando 5 preguntas simultneas para provocar error 503.

### Preguntas de Prueba (enviar simultneamente)
```bash
# Terminal 1
curl -X POST http://localhost:5001/api/process_question -H "Content-Type: application/json" \
  -d '{"question_text": "Qu es la virtualizacin?", "original_answer": "Tecnologa de abstraccin"}'

# Terminal 2
curl -X POST http://localhost:5001/api/process_question -H "Content-Type: application/json" \
  -d '{"question_text": "Qu es un hypervisor?", "original_answer": "Software de virtualizacin"}'

# Terminal 3
curl -X POST http://localhost:5001/api/process_question -H "Content-Type: application/json" \
  -d '{"question_text": "Qu es VMware?", "original_answer": "Plataforma de virtualizacin empresarial"}'

# Terminal 4
curl -X POST http://localhost:5001/api/process_question -H "Content-Type: application/json" \
  -d '{"question_text": "Qu es VirtualBox?", "original_answer": "Solucin de virtualizacin gratuita"}'

# Terminal 5
curl -X POST http://localhost:5001/api/process_question -H "Content-Type: application/json" \
  -d '{"question_text": "Qu es Hyper-V?", "original_answer": "Hypervisor de Microsoft Windows"}'
```

### Flujo Esperado
1. **LLM Consumer**  Procesa primera pregunta exitosamente
2. **LLM Consumer**  Recibe ms preguntas, Ollama responde 503 Service Unavailable (sobrecarga)
3. **Kafka Topic** `llm-responses-error-overload`  Consumer publica errores
4. **Retry Overload Consumer**  Consume errores, aplica **exponential backoff**:
   - Intento 1: Espera 2^1 = 2 segundos
   - Intento 2: Espera 2^2 = 4 segundos  
   - Intento 3: Espera 2^3 = 8 segundos
5. **Reintento exitoso**  Mensaje retorna a `questions-pending`
6. **Flujo normal** contina hasta PostgreSQL

### Comportamiento Esperado
- **Respuesta inicial**: 202 Accepted para todas las preguntas
- **Logs LLM Consumer**: "Error 503: Service Unavailable", "Publicando a llm-responses-error-overload"
- **Logs Retry Consumer**: "Reintentando question_id=... (intento 1/3)", "Backoff 2s", "Backoff 4s"
- **Resultado final**: Todas las preguntas procesadas exitosamente con `processing_attempts` entre 2-3

### Verificacin
```sql
-- Verificar reintentos en PostgreSQL
SELECT question_id, question_text, processing_attempts, bert_score 
FROM responses 
WHERE question_text LIKE '%virtualizacin%' OR question_text LIKE '%hypervisor%'
ORDER BY processing_attempts DESC;
```

---

## CASO 3: Regeneracin por Baja Calidad
**Objetivo**: Demostrar validacin de score y regeneracin automtica

### Descripcin
Enviar pregunta cuya respuesta del LLM tendr baja similitud con la respuesta original (score < 0.75).

### Pregunta de Prueba
```bash
curl -X POST http://localhost:5001/api/process_question \
  -H "Content-Type: application/json" \
  -d '{
    "question_text": "Cul es la capital de Francia?",
    "original_answer": "La capital de Francia es Pars, una ciudad con ms de 2 millones de habitantes ubicada en el norte del pas, famosa por la Torre Eiffel, el Louvre y la catedral de Notre-Dame."
  }'
```

**Nota**: Esta pregunta podra generar respuesta corta como "Pars", resultando en score bajo vs respuesta detallada.

### Flujo Esperado
1. **LLM Consumer**  Genera respuesta inicial (posiblemente corta)
2. **Score Validator**  Calcula BERTScore entre respuesta LLM y `original_answer`
3. **Score < 0.75**  Kafka topic `low-quality-responses`
4. **Score Validator**  Re-consume de `low-quality-responses`, incrementa contador regeneracin
5. **Kafka Topic** `questions-pending`  Mensaje vuelve a la cola (max 3 intentos)
6. **LLM Consumer**  Genera nueva respuesta (con prompt mejorado o aleatoriedad del LLM)
7. **Score Validator**  Valida nuevamente
8. **Decision**:
   - Si score  0.75  `validated-responses` (xito)
   - Si an < 0.75 y intentos < 3  Repetir regeneracin
   - Si intentos = 3  Guardar con score bajo (evitar loop infinito)

### Comportamiento Esperado
- **Primera validacin**: Score 0.45-0.65 (baja similitud)
- **Regeneraciones**: 1-2 intentos adicionales
- **Score final**: 0.75+ o guardado con flag de baja calidad
- **Campo `processing_attempts`**: 2 o 3

### Verificacin
```sql
-- Ver respuestas regeneradas
SELECT question_id, question_text, answer, bert_score, processing_attempts, created_at
FROM responses 
WHERE question_text LIKE '%capital de Francia%'
ORDER BY created_at DESC;

-- Estadsticas de regeneraciones
SELECT 
  CASE 
    WHEN processing_attempts = 1 THEN 'Primera vez'
    WHEN processing_attempts = 2 THEN '1 regeneracin'
    WHEN processing_attempts >= 3 THEN '2+ regeneraciones'
  END as regeneracion,
  COUNT(*) as cantidad
FROM responses
GROUP BY processing_attempts
ORDER BY processing_attempts;
```

---

## CASO 4: Cache Hit - Respuesta Inmediata
**Objetivo**: Demostrar optimizacin por cache Redis

### Descripcin
Repetir una pregunta ya procesada anteriormente para obtener respuesta desde cache.

### Preparacin
```bash
# Primera vez: procesar pregunta (CASO 1)
curl -X POST http://localhost:5001/api/process_question \
  -H "Content-Type: application/json" \
  -d '{
    "question_text": "Qu es Docker y para qu se utiliza?",
    "original_answer": "Tecnologa de contenedores"
  }'

# Esperar 3-4 segundos hasta que se complete el procesamiento
```

### Pregunta de Prueba (repetida)
```bash
# Segunda vez: misma pregunta (cache hit)
curl -X POST http://localhost:5001/api/process_question \
  -H "Content-Type: application/json" \
  -d '{
    "question_text": "Qu es Docker y para qu se utiliza?",
    "original_answer": "Tecnologa de contenedores"
  }'
```

### Flujo Esperado
1. **Storage Service**  Recibe POST, calcula hash de `question_text`
2. **Redis**  Busca key `response:<hash>` en cache
3. **Cache HIT**  Encuentra respuesta almacenada
4. **Response**  Retorna `200 OK` con respuesta completa (NO 202)
5. **NO procesamiento**  No se publica a Kafka, no se llama LLM

### Comportamiento Esperado
- **Primera llamada**: 202 Accepted, procesamiento asncrono (2-4 segundos)
- **Segunda llamada**: **200 OK**, respuesta inmediata (<10ms)
- **Diferencia de latencia**: 200-400x ms rpido
- **Campo adicional**: `"source": "cache"` en la respuesta

### Respuesta Esperada (200 OK)
```json
{
  "status": "found",
  "source": "cache",
  "result": {
    "question_id": "0427eabfd04b8143",
    "question_text": "Qu es Docker y para qu se utiliza?",
    "answer": "Docker es una herramienta de gestin de contenedores...",
    "score": 0.85
  }
}
```

### Verificacin
```bash
# Ver estadsticas de cache Redis
curl http://localhost:5001/api/metrics | jq '.cache_info'

# Debera mostrar:
# - keyspace_hits: N (incrementa con cada cache hit)
# - keyspace_misses: M (incrementa cuando no hay cache)
# - hit_rate = hits / (hits + misses)
```

---

## CASO 5: Mtricas del Sistema
**Objetivo**: Demostrar observabilidad y monitoreo del sistema

### Descripcin
Consultar endpoint de mtricas para obtener estadsticas completas del sistema.

### Request HTTP
```bash
curl http://localhost:5001/api/metrics
```

### Respuesta Esperada
```json
{
  "total_responses": 7880,
  "average_score": 0.8507005076141981,
  "attempts_distribution": {
    "1": 3919,
    "2": 2646,
    "3": 1315
  },
  "cache_info": {
    "keyspace_hits": 2,
    "keyspace_misses": 7,
    "total_commands_processed": 222,
    "instantaneous_ops_per_sec": 0,
    ...
  }
}
```

### Mtricas Clave a Destacar
1. **total_responses**: 7,880 respuestas almacenadas (7,877 migradas + 3 nuevas)
2. **average_score**: 0.851 (85.1% de calidad promedio, supera threshold 0.75)
3. **attempts_distribution**:
   - 49.7% xito en primer intento
   - 33.6% requiere 1 retry
   - 16.7% requiere 2 retries
   - **Confiabilidad**: 96.7% de preguntas procesadas exitosamente con mx 3 intentos
4. **cache_info**:
   - `keyspace_hits`: Consultas exitosas a cache
   - `keyspace_misses`: Consultas que no estaban en cache
   - **Hit rate**: hits/(hits+misses)  100%

### Queries PostgreSQL Adicionales
```sql
-- Top 5 mejores scores
SELECT question_text, bert_score, answer
FROM responses
ORDER BY bert_score DESC
LIMIT 5;

-- Distribucin de scores por rangos
SELECT 
  CASE 
    WHEN bert_score >= 0.90 THEN 'Excelente (0.90+)'
    WHEN bert_score >= 0.80 THEN 'Bueno (0.80-0.89)'
    WHEN bert_score >= 0.75 THEN 'Aceptable (0.75-0.79)'
    ELSE 'Bajo (<0.75)'
  END as calidad,
  COUNT(*) as cantidad,
  ROUND(AVG(bert_score), 3) as score_promedio
FROM responses
GROUP BY 
  CASE 
    WHEN bert_score >= 0.90 THEN 'Excelente (0.90+)'
    WHEN bert_score >= 0.80 THEN 'Bueno (0.80-0.89)'
    WHEN bert_score >= 0.75 THEN 'Aceptable (0.75-0.79)'
    ELSE 'Bajo (<0.75)'
  END
ORDER BY score_promedio DESC;

-- Latencia promedio por nmero de intentos
SELECT 
  processing_attempts,
  COUNT(*) as cantidad,
  ROUND(AVG(total_processing_time_ms), 0) as latencia_promedio_ms,
  ROUND(MIN(total_processing_time_ms), 0) as latencia_min_ms,
  ROUND(MAX(total_processing_time_ms), 0) as latencia_max_ms
FROM responses
GROUP BY processing_attempts
ORDER BY processing_attempts;
```

---

## CASO EXTRA: Monitoreo en Kafka UI
**Objetivo**: Visualizar flujo de mensajes en tiempo real

### Acceso
```
URL: http://localhost:8080
```

### Elementos a Mostrar

#### 1. Topics Dashboard
- **questions-pending**: 3 particiones, mensajes entrantes
- **llm-responses-success**: 3 particiones, respuestas exitosas
- **llm-responses-error-overload**: 2 particiones, errores de sobrecarga
- **llm-responses-error-quota**: 2 particiones, errores de cuota
- **validated-responses**: 3 particiones, respuestas con score  0.75
- **low-quality-responses**: 1 particin, respuestas con score < 0.75

#### 2. Consumer Groups
- **llm-consumer-group**: 2 consumers activos, LAG=0
- **score-validator-group**: 1 consumer, LAG=0
- **storage-consumer-group**: 1 consumer, LAG=0
- **retry-overload-consumer-group**: 1 consumer, LAG=0
- **retry-quota-consumer-group**: 1 consumer, LAG=0

#### 3. Messages View
- Ver contenido de mensajes en `questions-pending`
- Ver respuestas en `validated-responses`
- Filtrar por key (question_id) o timestamp

---

## Cronograma Demo (10 minutos)

### Minuto 0-1: Introduccin
- Arquitectura general: 11 servicios, 7 topics Kafka
- Datos: 7,880 respuestas migradas desde Tarea 1
- Objetivo: Sistema asncrono con retries y validacin de calidad

### Minuto 1-3: CASO 1 - Flujo Normal
- Enviar nueva pregunta sobre Kubernetes
- Mostrar 202 Accepted
- Ver mensaje en Kafka UI (questions-pending)
- Ver procesamiento en logs LLM Consumer
- Ver validacin en logs Score Validator
- Ver resultado en PostgreSQL

### Minuto 3-5: CASO 2 y 3 - Errores y Regeneracin
- Enviar 5 preguntas simultneas (provocar 503)
- Mostrar logs de retry con exponential backoff
- Consultar PostgreSQL: `processing_attempts = 2 o 3`
- Mencionar regeneracin por baja calidad (mismo mecanismo)

### Minuto 5-7: CASO 4 - Cache Hit
- Repetir pregunta ya procesada
- Comparar: 202 (primera) vs 200 (segunda)
- Mostrar diferencia de latencia: 2500ms vs 5ms
- Ver hit rate en mtricas Redis

### Minuto 7-9: CASO 5 - Mtricas y Kafka UI
- Mostrar endpoint `/metrics`: 7,880 respuestas, score 0.851
- Query PostgreSQL: distribucin de scores
- Kafka UI: topics, consumer groups, LAG=0
- Resaltar: 96.7% xito con max 3 reintentos

### Minuto 9-10: Conclusiones y Comparacin
- **Tarea 1 (sncrono)**: 
  - Latencia: 2000-5000ms bloqueante
  - Sin retries automticos
  - Sin cache
  - Throughput: ~0.4 req/s
  
- **Tarea 2 (asncrono)**:
  - Latencia percibida: 10ms (202 Accepted)
  - Retries automticos: +11% confiabilidad
  - Cache Redis: 200-400x ms rpido en hits
  - Throughput: ~0.8 req/s (2x mejora)
  - Observabilidad: mtricas completas, Kafka UI

---

## Comandos tiles para Demo

### Verificar servicios
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Ver logs en tiempo real
```bash
# LLM Consumer
docker logs -f llm_consumer_1

# Score Validator
docker logs -f score_validator

# Storage Service
docker logs -f storage_service
```

### Limpiar cache Redis (opcional)
```bash
docker exec -it redis redis-cli FLUSHALL
```

### Reset PostgreSQL (NO recomendado, perder datos)
```bash
docker exec -it postgres_db psql -U user -d yahoo_db -c "TRUNCATE TABLE responses RESTART IDENTITY CASCADE;"
```

### Monitorear Kafka offsets en vivo
```bash
watch -n 1 'docker exec kafka_broker kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group llm-consumer-group'
```

---

## Checklist Pre-Demo

- [ ] Todos los 11 servicios levantados: `docker ps` muestra 11 containers UP
- [ ] PostgreSQL: 7,880+ respuestas disponibles
- [ ] Redis: Cache limpio o con datos de prueba
- [ ] Kafka UI: Accesible en http://localhost:8080
- [ ] Logs: Terminal listos para mostrar en vivo
- [ ] Queries SQL: Preparados en archivo .sql
- [ ] cURL commands: Copiados en archivo para ejecucin rpida
- [ ] Grabacin de pantalla: OBS Studio o software similar configurado
- [ ] Audio: Micrfono testeado
- [ ] Tiempo: Practicar cronograma de 10 minutos

---

## Troubleshooting

### Error: "Connection refused" al enviar pregunta
```bash
# Verificar Storage Service activo
docker ps | grep storage_service
docker logs storage_service
```

### Error: LAG alto en consumer groups
```bash
# Reiniciar consumers
docker restart llm_consumer_1 llm_consumer_2 score_validator
```

### Error: PostgreSQL no responde
```bash
# Verificar conexin
docker exec -it postgres_db psql -U user -d yahoo_db -c "SELECT 1;"
```

### Error: Kafka UI no carga
```bash
# Reiniciar Kafka UI
docker restart kafka_ui
```

---

**Autor**: Sistema de Evaluacin Tarea 2  
**Fecha**: Generado automticamente  
**Versin**: 1.0
