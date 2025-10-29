# Tarea 2: Arquitectura Asncrona con Kafka y Flink

## Diagrama de Flujo General

```
[Generador Trfico] 
       
[Almacenamiento/BDD]
              
[Cache]  [Respuesta Directa]
   
[No existe]
   
[Kafka: questions-pending]
   
[Consumidor LLM]
                         
[Success]  [Overload]  [Quota]
                         
[Kafka]    [Retry]    [Retry]
   
[Flink: Score Analysis]
              
[OK]     [Low Quality]
              
[validated] [questions-pending]
   
[Almacenamiento]
```

## Topologa de Tpicos Kafka

### 1. `questions-pending`
**Propsito**: Cola principal de preguntas que necesitan ser procesadas por el LLM.
- **Productores**: 
  - Mdulo de Almacenamiento (cuando no encuentra respuesta en BDD)
  - Flink (cuando detecta respuesta de baja calidad para reintento)
- **Consumidores**: 
  - Servicio LLM (consume y enva peticin al modelo)

**Estructura del mensaje**:
```json
{
  "question_id": "uuid",
  "question_text": "texto de la pregunta",
  "retry_count": 0,
  "timestamp": "ISO8601",
  "original_answer": "respuesta de Yahoo si existe"
}
```

### 2. `llm-responses-success`
**Propsito**: Respuestas exitosas del LLM que requieren validacin de calidad.
- **Productores**: Servicio LLM (cuando obtiene respuesta exitosa)
- **Consumidores**: Flink (para calcular score y decidir)

**Estructura del mensaje**:
```json
{
  "question_id": "uuid",
  "question_text": "texto",
  "llm_response": "respuesta del LLM",
  "original_answer": "respuesta Yahoo",
  "retry_count": 0,
  "response_time_ms": 1234,
  "timestamp": "ISO8601"
}
```

### 3. `llm-responses-error-overload`
**Propsito**: Errores por sobrecarga del modelo (HTTP 503, 429).
- **Productores**: Servicio LLM
- **Consumidores**: Consumidor de Reintentos con Exponential Backoff

**Estructura del mensaje**:
```json
{
  "question_id": "uuid",
  "question_text": "texto",
  "error_type": "overload",
  "retry_count": 0,
  "error_message": "detalles del error",
  "timestamp": "ISO8601"
}
```

**Estrategia de reintento**: Exponential Backoff
- 1er reintento: 2 segundos
- 2do reintento: 4 segundos
- 3er reintento: 8 segundos
- Mximo: 3 reintentos

### 4. `llm-responses-error-quota`
**Propsito**: Errores por lmite de cuota (HTTP 402, quota exceeded).
- **Productores**: Servicio LLM
- **Consumidores**: Consumidor de Reintentos con Delay Fijo

**Estructura del mensaje**:
```json
{
  "question_id": "uuid",
  "question_text": "texto",
  "error_type": "quota",
  "retry_count": 0,
  "retry_after_seconds": 60,
  "timestamp": "ISO8601"
}
```

**Estrategia de reintento**: Fixed Delay
- Espera 60 segundos antes de reintentar
- Mximo: 5 reintentos

### 5. `validated-responses`
**Propsito**: Respuestas que pasaron la validacin de calidad y estn listas para persistir.
- **Productores**: Flink (cuando score > umbral)
- **Consumidores**: Mdulo de Almacenamiento (persiste en PostgreSQL)

**Estructura del mensaje**:
```json
{
  "question_id": "uuid",
  "question_text": "texto",
  "llm_response": "respuesta validada",
  "original_answer": "respuesta Yahoo",
  "bert_score": 0.89,
  "processing_attempts": 1,
  "total_processing_time_ms": 2345,
  "timestamp": "ISO8601"
}
```

### 6. `low-quality-responses` (opcional, para mtricas)
**Propsito**: Registro de respuestas rechazadas para anlisis.
- **Productores**: Flink
- **Consumidores**: Sistema de mtricas/logging

## Componentes del Sistema

### Servicio LLM Asncrono (`llm_consumer_service`)
**Responsabilidades**:
1. Consumir mensajes de `questions-pending`
2. Llamar a Ollama API
3. Clasificar respuesta (xito, overload, quota, otro error)
4. Producir a tpico correspondiente

**Manejo de Errores**:
- **503 Service Unavailable**  `llm-responses-error-overload`
- **429 Too Many Requests**  `llm-responses-error-overload`
- **402 Payment Required**  `llm-responses-error-quota`
- **200 OK**  `llm-responses-success`
- **Otros errores**  Log y descarte (o tpico de errores fatales)

### Consumidores de Reintento
**Exponential Backoff Consumer** (`retry_overload_consumer`):
- Consume de `llm-responses-error-overload`
- Aplica backoff exponencial: 2^retry_count segundos
- Reenva a `questions-pending` incrementando retry_count
- Si retry_count > 3, registra fallo permanente

**Quota Retry Consumer** (`retry_quota_consumer`):
- Consume de `llm-responses-error-quota`
- Espera tiempo fijo (60s) o usa header Retry-After
- Reenva a `questions-pending`
- Si retry_count > 5, registra fallo permanente

### Flink Job: Score Validator (`flink_score_job`)
**Responsabilidades**:
1. Consumir de `llm-responses-success`
2. Calcular BERTScore entre llm_response y original_answer
3. Comparar con umbral definido
4. Decidir flujo:
   - Si score >= umbral  `validated-responses`
   - Si score < umbral Y retry_count < 3  `questions-pending` (incrementar retry_count)
   - Si score < umbral Y retry_count >= 3  `validated-responses` (aceptar como mejor intento)

**Definicin de Umbral**:
- **Umbral propuesto**: 0.75 (BERTScore F1)
- **Justificacin**: 
  - Valores < 0.70 indican respuestas semnticamente muy diferentes
  - Valores > 0.80 son casi perfectos (difcil de alcanzar con LLM pequeo)
  - 0.75 balancea calidad vs reintentos excesivos

**Mtricas a registrar**:
- Score promedio antes/despus de regeneracin
- Tasa de regeneracin (% de respuestas que necesitaron reintento)
- Mejora promedio de score tras regeneracin
- Nmero de llamadas adicionales al LLM

### Mdulo de Almacenamiento Adaptado
**Flujo**:
1. **Consulta inicial**: Verificar PostgreSQL por question_id/hash
2. **Si existe**: 
   - Retornar respuesta directamente
   - (Opcional) Poblar Redis cache
3. **Si no existe**: 
   - Producir mensaje a `questions-pending`
   - Retornar estado "pending" al generador de trfico
4. **Consumidor**: 
   - Leer de `validated-responses`
   - Persistir en PostgreSQL
   - Invalidar/actualizar cache si aplica

### Generador de Trfico Adaptado
**Cambios necesarios**:
1. Consultar almacenamiento como antes
2. Manejar respuestas asncronas:
   - Estado "found": Respuesta disponible inmediatamente
   - Estado "pending": En proceso, esperando resultado
   - Estado "error": Fallo permanente
3. Implementar polling o callback para resultados pendientes
4. Registrar latencia real vs latencia percibida

## Prevencin de Ciclos Infinitos

**Mecanismo**: Campo `retry_count` en todos los mensajes
- **Lmite duro**: Mximo 3 reintentos por pregunta
- **Control en mltiples puntos**:
  1. Consumidor LLM: Verificar retry_count antes de procesar
  2. Flink: Solo reenviar si retry_count < 3
  3. Consumidores de reintento: Descartar si retry_count >= lmite

**Registro de fallos permanentes**:
- Tabla PostgreSQL: `failed_questions`
- Columnas: question_id, retry_count, last_error, last_attempt_timestamp
- Usar para anlisis post-mortem y mejoras del sistema

## Anlisis de Trade-offs

### Ventajas del Modelo Asncrono
1. **Desacoplamiento**: Servicios independientes, fcil escalado horizontal
2. **Resiliencia**: Fallos en LLM no bloquean todo el sistema
3. **Throughput**: Cola acumula trabajo, procesamiento continuo
4. **Gestin de picos**: Kafka buffer para cargas variables
5. **Recuperacin**: Mensajes persistidos, no se pierden en reinicio

### Desventajas del Modelo Asncrono
1. **Latencia percibida**: Usuario debe esperar (no respuesta inmediata)
2. **Complejidad**: Ms componentes, ms puntos de fallo potenciales
3. **Debugging**: Flujo distribuido ms difcil de trazar
4. **Consistencia eventual**: Datos tardan en propagarse
5. **Sobrecarga**: Serializacin, red, overhead de mensajera

### Impacto en Mtricas
- **Latencia E2E**: Aumenta (procesamiento asncrono + colas)
- **Latencia del usuario**: Puede mejorar si usa polling inteligente
- **Throughput**: Aumenta significativamente (procesamiento paralelo)
- **Tasa de xito**: Mejora (reintentos automticos)
- **Utilizacin de recursos**: Ms eficiente (no espera ociosa)

## Mtricas Clave a Recolectar

### Sistema Kafka
- Lag de consumidores (mensajes pendientes por tpico)
- Throughput por tpico (msg/s)
- Latencia produccin/consumo
- Tamao de colas

### Servicio LLM
- Tasa de xito/error (breakdown por tipo)
- Latencia por peticin
- Reintentos necesarios vs exitosos
- Distribucin de errores

### Flink
- Score promedio de respuestas (primera generacin)
- Score promedio tras regeneracin
- Tasa de regeneracin (%)
- Mejora promedio de score
- Costo computacional (llamadas adicionales al LLM)
- Watermark y event-time processing lag

### Sistema Global
- Latencia E2E promedio
- Throughput total (preguntas procesadas/segundo)
- Tasa de fallos permanentes
- Tiempo promedio en cada etapa del pipeline

## Prximos Pasos

1.  Definir arquitectura y topologa Kafka
2.  Configurar infraestructura (docker-compose)
3.  Implementar servicio consumidor LLM
4.  Implementar consumidores de reintento
5.  Desarrollar job Flink
6.  Adaptar mdulo de almacenamiento
7.  Adaptar generador de trfico
8.  Implementar sistema de mtricas
9.  Testing y validacin
10.  Documentacin y anlisis de resultados
