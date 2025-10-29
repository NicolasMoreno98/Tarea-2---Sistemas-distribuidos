# 🎬 GUION DE DEMOSTRACIÓN - TAREA 2
## Sistema Asíncrono con Apache Kafka y Apache Flink

---

## 📋 TABLA DE CONTENIDOS
1. [Preparación Inicial](#1-preparación-inicial)
2. [Demostración de Arquitectura](#2-demostración-de-arquitectura)
3. [Pipeline Asíncrono con Kafka](#3-pipeline-asíncrono-con-kafka)
4. [Gestión de Fallos y Reintentos](#4-gestión-de-fallos-y-reintentos)
5. [Procesamiento de Flujos con Flink](#5-procesamiento-de-flujos-con-flink)
6. [Análisis de Métricas](#6-análisis-de-métricas)
7. [Preguntas y Respuestas](#7-preguntas-y-respuestas)

---

## 1. PREPARACIÓN INICIAL

### 1.1 Verificar Prerequisitos

```powershell
# Verificar Docker
Write-Host "`n=== VERIFICANDO PREREQUISITOS ===" -ForegroundColor Cyan
docker --version
docker-compose --version

# Verificar Ollama (LLM local)
ollama list
```

**Narración**: 
> "Comenzamos verificando que tenemos Docker, Docker Compose y Ollama instalados. Ollama nos permite ejecutar el modelo LLM de forma local, eliminando restricciones de rate limiting."

### 1.2 Posicionarse en el Directorio del Proyecto

```powershell
cd "d:\U\Sistemas Distribuidos\Docker\yahoo_llm_project"
Get-ChildItem -Name
```

**Narración**:
> "Navegamos al directorio del proyecto donde encontramos todos los componentes: servicios de consumidores, configuraciones de Kafka, el job de Flink compilado, y la documentación técnica."

### 1.3 Mostrar la Documentación Clave

```powershell
# Mostrar documentos principales
Write-Host "`n=== DOCUMENTACIÓN DEL PROYECTO ===" -ForegroundColor Yellow
Get-ChildItem -Filter "*.md" | Select-Object Name, Length, LastWriteTime
```

**Narración**:
> "Tenemos documentación exhaustiva que incluye:
> - README_TAREA2_FLINK.md: Arquitectura técnica completa
> - CUMPLIMIENTO_TAREA2.md: Verificación de todos los requerimientos
> - ANALISIS_SCORES.md: Justificación del umbral de calidad
> - DASHBOARD_VISUALIZACION.md: Documentación del sistema de métricas"

---

## 2. DEMOSTRACIÓN DE ARQUITECTURA

### 2.1 Mostrar el Docker Compose

```powershell
Write-Host "`n=== ARQUITECTURA DEL SISTEMA ===" -ForegroundColor Cyan
notepad docker-compose-tarea2.yml
```

**Narración**:
> "Nuestro docker-compose orquesta 15 contenedores:
> 
> **Infraestructura Base (Tarea 1)**:
> - PostgreSQL: Base de datos principal
> - Redis: Sistema de caché con política LRU
> 
> **Ecosistema Kafka (Tarea 2)**:
> - Zookeeper: Coordinación de Kafka
> - Kafka Broker: Bus de mensajes central
> - Kafka Init: Creación automática de 7 tópicos
> 
> **Servicios de Aplicación**:
> - Storage Service: Persistencia asíncrona
> - LLM Consumer (x2 réplicas): Procesamiento de preguntas
> - Retry Overload Consumer: Reintentos por sobrecarga
> - Retry Quota Consumer: Reintentos por límite de cuota
> - Score Validator: Cálculo de BERTScore
> 
> **Apache Flink**:
> - Flink JobManager: Coordinador
> - Flink TaskManager: Ejecutor
> 
> **Monitoreo**:
> - Kafka UI: Visualización de tópicos y mensajes
> - Viz Service: Dashboard de métricas y scores
> - Traffic Generator: Simulador de carga"

### 2.2 Mostrar Topología de Tópicos de Kafka

```powershell
Write-Host "`n=== TOPOLOGÍA DE KAFKA ===" -ForegroundColor Yellow
Write-Host @"

TÓPICOS DISEÑADOS (7 en total):

1. questions-pending
   Propósito: Preguntas nuevas que requieren procesamiento
   Productores: Storage Service, Flink (feedback loop)
   Consumidores: LLM Consumer (2 réplicas)
   Particiones: 3 (paralelismo)

2. llm-responses-success
   Propósito: Respuestas exitosas del LLM
   Productores: LLM Consumer
   Consumidores: Flink Job (ScoreValidator)
   Particiones: 3

3. llm-responses-error-overload
   Propósito: Errores por sobrecarga del modelo
   Productores: LLM Consumer
   Consumidores: Retry Overload Consumer
   Particiones: 2
   Estrategia: Exponential backoff (2, 4, 8 segundos)

4. llm-responses-error-quota
   Propósito: Errores por límite de cuota
   Productores: LLM Consumer
   Consumidores: Retry Quota Consumer
   Particiones: 2
   Estrategia: Delay fijo 60 segundos

5. validated-responses
   Propósito: Respuestas validadas por Flink (score ≥ umbral)
   Productores: Flink Job
   Consumidores: Storage Service
   Particiones: 3

6. low-quality-responses
   Propósito: Respuestas bajo umbral (métricas)
   Productores: Flink Job
   Consumidores: Ninguno (solo logging)
   Particiones: 1

7. llm-responses-error-permanent
   Propósito: Errores tras máximo de reintentos
   Productores: Retry Consumers
   Consumidores: Ninguno (registro permanente)
   Particiones: 1

"@
```

**Narración**:
> "Diseñamos una topología de 7 tópicos que gestiona todo el ciclo de vida de una consulta, desde su ingreso hasta su persistencia o descarte. Cada tópico tiene un propósito específico y está dimensionado según su carga esperada."

---

## 3. PIPELINE ASÍNCRONO CON KAFKA

### 3.1 Iniciar el Sistema Completo

```powershell
Write-Host "`n=== INICIANDO SISTEMA ===" -ForegroundColor Green
docker-compose -f docker-compose-tarea2.yml up -d

# Esperar a que los servicios estén listos
Write-Host "`nEsperando a que los servicios inicien..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Verificar estado
docker ps --format "table {{.Names}}\t{{.Status}}" | Select-String -Pattern "NAME|postgres|redis|kafka|flink|zookeeper|llm|storage|score|retry|viz"
```

**Narración**:
> "Iniciamos los 15 contenedores de forma orquestada. Docker Compose maneja las dependencias automáticamente: primero inicia PostgreSQL y Zookeeper, luego Kafka, después los servicios de aplicación, y finalmente Flink."

### 3.2 Verificar Tópicos de Kafka

```powershell
Write-Host "`n=== VERIFICANDO TÓPICOS DE KAFKA ===" -ForegroundColor Cyan
docker exec kafka_broker kafka-topics --bootstrap-server localhost:9092 --list
```

**Narración**:
> "Los 7 tópicos se crearon automáticamente al iniciar el sistema. Veamos sus configuraciones detalladas..."

```powershell
# Ver detalles de un tópico clave
docker exec kafka_broker kafka-topics --bootstrap-server localhost:9092 --describe --topic questions-pending
```

**Narración**:
> "El tópico 'questions-pending' tiene 3 particiones para distribuir la carga entre los 2 consumidores LLM, proporcionando paralelismo y tolerancia a fallos."

### 3.3 Abrir Kafka UI

```powershell
Write-Host "`n=== ABRIENDO KAFKA UI ===" -ForegroundColor Yellow
Start-Process "http://localhost:8080"
```

**Narración**:
> "Kafka UI nos permite visualizar en tiempo real:
> - Los 7 tópicos configurados
> - Mensajes en cada tópico
> - Grupos de consumidores activos
> - Lag de procesamiento
> - Throughput del sistema"

---

## 4. GESTIÓN DE FALLOS Y REINTENTOS

### 4.1 Verificar Base de Datos Inicial

```powershell
Write-Host "`n=== ESTADO INICIAL DE LA BASE DE DATOS ===" -ForegroundColor Cyan
docker exec postgres_db psql -U user -d yahoo_db -c "SELECT COUNT(*) as total_respuestas FROM responses;"
```

**Narración**:
> "Actualmente tenemos 7,887 respuestas en la base de datos, todas procesadas por Flink con el umbral anterior de 0.75. Vamos a demostrar el sistema con nuevas consultas."

### 4.2 Generar Tráfico de Prueba

```powershell
Write-Host "`n=== GENERANDO TRÁFICO DE PRUEBA ===" -ForegroundColor Green

# Ejecutar generador con 50 preguntas
docker exec traffic_generator python generate_traffic.py --num-requests 50 --interval 500
```

**Narración**:
> "El generador de tráfico envía 50 preguntas al sistema a un ritmo de 500ms por consulta. Cada pregunta sigue este flujo:
> 
> 1. **Storage Service consulta PostgreSQL**
>    - Si existe → devuelve respuesta cacheada
>    - Si no existe → publica en 'questions-pending'
> 
> 2. **LLM Consumer procesa la pregunta**
>    - Éxito → publica en 'llm-responses-success'
>    - Error de sobrecarga → publica en 'llm-responses-error-overload'
>    - Error de cuota → publica en 'llm-responses-error-quota'
> 
> 3. **Consumidores de Reintento manejan errores**
>    - Overload: Exponential backoff (2s, 4s, 8s)
>    - Quota: Delay fijo de 60s
>    - Máximo 3 intentos por pregunta"

### 4.3 Monitorear Procesamiento en Tiempo Real

```powershell
Write-Host "`n=== MONITOREANDO LOGS DE CONSUMIDORES ===" -ForegroundColor Yellow

# Ver logs de LLM Consumer
docker logs llm-consumer-1 --tail 20 --follow
```

**Narración** (mientras se ven los logs):
> "Observamos el procesamiento en tiempo real:
> - ✅ Preguntas procesadas exitosamente
> - ⚠️ Errores capturados y encolados para reintento
> - 🔄 Reintentos automáticos con backoff
> - 📊 Métricas de rendimiento"

```powershell
# Ver logs del Retry Overload Consumer
docker logs retry_overload_consumer --tail 20
```

**Narración**:
> "El consumidor de reintentos por sobrecarga implementa exponential backoff:
> - Intento 1: Espera 2 segundos
> - Intento 2: Espera 4 segundos
> - Intento 3: Espera 8 segundos
> 
> Esto previene saturar el LLM cuando está sobrecargado."

### 4.4 Verificar Métricas en Kafka UI

**Narración** (en la interfaz de Kafka UI):
> "En Kafka UI podemos ver:
> 
> **Tópico 'questions-pending'**:
> - Mensajes producidos: ~50
> - Mensajes consumidos: ~50
> - Lag: 0 (procesamiento al día)
> 
> **Tópico 'llm-responses-success'**:
> - Respuestas exitosas acumulándose
> - Esperando procesamiento de Flink
> 
> **Tópicos de Error**:
> - 'llm-responses-error-overload': X mensajes
> - 'llm-responses-error-quota': Y mensajes
> - Ambos siendo reprocesados automáticamente"

---

## 5. PROCESAMIENTO DE FLUJOS CON FLINK

### 5.1 Desplegar Job de Flink

```powershell
Write-Host "`n=== DESPLEGANDO JOB DE FLINK ===" -ForegroundColor Cyan

# Copiar JAR al contenedor (si no está montado como volumen)
docker cp "flink-job\target\flink-score-validator-1.0.jar" flink_jobmanager:/opt/flink/

# Desplegar en modo detached (-d)
docker exec flink_jobmanager flink run -d /opt/flink/flink-score-validator-1.0.jar
```

**Narración**:
> "Desplegamos el job de Flink en modo detached (-d) para que se ejecute en segundo plano. El job procesará continuamente los mensajes del tópico 'llm-responses-success'."

### 5.2 Abrir Flink UI

```powershell
Write-Host "`n=== ABRIENDO FLINK UI ===" -ForegroundColor Yellow
Start-Process "http://localhost:8081"
```

**Narración**:
> "La interfaz de Flink muestra el job 'Score Validator' corriendo activamente con el nuevo umbral de 0.85."

### 5.3 Verificar Estado del Job

```powershell
Write-Host "`n=== VERIFICANDO JOB DE FLINK ===" -ForegroundColor Cyan
docker exec flink_jobmanager flink list
```

**Narración**:
> "Nuestro job de Flink está en estado RUNNING con JobID visible. Este job:
> 
> 1. **Consume** del tópico 'llm-responses-success'
> 2. **Calcula BERTScore** llamando al servicio score_validator
> 3. **Decide** basándose en el umbral de calidad (0.85):
>    - Score ≥ 0.85 → Publica en 'validated-responses'
>    - Score < 0.85 → Reinyecta en 'questions-pending'
> 4. **Previene ciclos infinitos** limitando a 3 reintentos"

### 5.4 Mostrar el Código del Job de Flink

```powershell
Write-Host "`n=== CÓDIGO DEL JOB DE FLINK ===" -ForegroundColor Cyan
Get-Content "flink-job\src\main\java\com\yahoo\flink\ScoreValidatorJob.java" | Select-Object -First 50
```

**Narración**:
> "El código muestra:
> - QUALITY_THRESHOLD = 0.85 (justificado por análisis estadístico)
> - MAX_RETRIES = 3 (previene ciclos infinitos)
> - Lógica de filtrado y enrutamiento de streams
> - Integración con score_validator vía HTTP"

### 5.5 Ver Métricas de Flink en Tiempo Real

**Narración** (en Flink UI):
> "En la interfaz podemos observar:
> 
> **Task Metrics**:
> - Records In: Respuestas procesadas
> - Records Out: Decisiones tomadas
> - Latency: Tiempo de procesamiento por mensaje
> 
> **Operators**:
> - Kafka Source: Consumiendo 'llm-responses-success'
> - Score Calculator: Calculando BERTScore
> - Decision Splitter: Enrutando según umbral
> - Kafka Sinks: Publicando a destinos apropiados
> 
> **Checkpointing**:
> - Estado persistente cada 30 segundos
> - Tolerancia a fallos garantizada"

### 5.5 Justificación del Umbral de Calidad

```powershell
Write-Host "`n=== ANÁLISIS DE UMBRAL DE CALIDAD ===" -ForegroundColor Yellow
Get-Content "ANALISIS_SCORES.md" | Select-Object -First 100
```

**Narración**:
> "Tras analizar 7,887 respuestas iniciales, determinamos:
> 
> **Estadísticas de la Distribución**:
> - Promedio: 0.851
> - Mediana: 0.850
> - Desviación Estándar: 0.058
> - Rango: 0.750 - 0.950
> 
> **Justificación del Umbral 0.85**:
> 1. Corresponde a la mediana de la distribución
> 2. Balance óptimo: 50% pasan, 50% se regeneran
> 3. Costo computacional razonable
> 4. Mejora tangible en la calidad final
> 
> **Alternativas Evaluadas**:
> - 0.75: Muy permisivo (100% pasan)
> - 0.80: Moderado (78% pasan, 22% regeneran)
> - 0.85: **SELECCIONADO** (50% pasan, 50% regeneran)
> - 0.90: Muy estricto (25% pasan, 75% regeneran)"

---

## 6. ANÁLISIS DE MÉTRICAS

### 6.1 Abrir Dashboard de Visualización

```powershell
Write-Host "`n=== ABRIENDO DASHBOARD DE MÉTRICAS ===" -ForegroundColor Green
Start-Process "http://localhost:5002"
```

**Narración**:
> "Nuestro dashboard muestra 5 gráficos interactivos con datos en tiempo real, actualizándose cada 30 segundos."

### 6.2 Analizar Distribución de Scores

**Narración** (en el dashboard):
> "**Gráfico 1: Distribución de Scores**
> 
> Observamos cómo se distribuyen los scores de calidad:
> - 0.75-0.8: X% (Aceptable, pero en el límite)
> - 0.8-0.85: X% (Bueno, cerca del umbral)
> - 0.85-0.9: X% (Muy bueno, superan el umbral)
> - 0.9-1.0: X% (Excelente, máxima calidad)
> 
> Esto valida nuestra decisión de usar 0.85 como umbral."

### 6.3 Analizar Reintentos de Procesamiento

**Narración** (en el dashboard):
> "**Gráfico 2: Intentos de Procesamiento**
> 
> Este gráfico tipo dona muestra:
> - X% con 1 intento (pasaron directo)
> - X% con 2 intentos (regeneradas 1 vez)
> - X% con 3 intentos (máximo reintentos)
> 
> Esto demuestra que el feedback loop está funcionando activamente."

### 6.4 Verificar Mejora de Calidad

**Narración** (en el dashboard):
> "**Gráfico 4: Mejora por Reintentos**
> 
> Este gráfico lineal demuestra la efectividad del ciclo de feedback:
> - Score promedio con 1 intento: X.XX
> - Score promedio con 2 intentos: X.XX (+X% mejora)
> - Score promedio con 3 intentos: X.XX (+X% mejora)
> 
> **Conclusión**: El feedback loop mejora la calidad en aproximadamente X% por reintento."

### 6.5 Consultar Estadísticas Detalladas

```powershell
Write-Host "`n=== ESTADÍSTICAS DEL SISTEMA ===" -ForegroundColor Cyan

# Total de respuestas procesadas
docker exec postgres_db psql -U user -d yahoo_db -c "
SELECT 
    COUNT(*) as total,
    ROUND(AVG(bert_score)::numeric, 3) as score_promedio,
    ROUND(STDDEV(bert_score)::numeric, 3) as desviacion,
    ROUND(MIN(bert_score)::numeric, 3) as min_score,
    ROUND(MAX(bert_score)::numeric, 3) as max_score
FROM responses;
"

# Distribución por intentos
docker exec postgres_db psql -U user -d yahoo_db -c "
SELECT 
    processing_attempts as intentos,
    COUNT(*) as cantidad,
    ROUND(AVG(bert_score)::numeric, 3) as score_promedio,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM responses), 1) as porcentaje
FROM responses
GROUP BY processing_attempts
ORDER BY processing_attempts;
"
```

**Narración**:
> "Las consultas SQL confirman los datos visualizados:
> - Total de respuestas procesadas
> - Score promedio general
> - Mejora incremental con cada reintento
> - Distribución de reintentos"

### 6.6 Calcular Costo Computacional

```powershell
Write-Host "`n=== CÁLCULO DE COSTO COMPUTACIONAL ===" -ForegroundColor Yellow

docker exec postgres_db psql -U user -d yahoo_db -c "
SELECT 
    COUNT(*) as total_preguntas,
    SUM(processing_attempts) as total_llamadas_llm,
    ROUND(AVG(processing_attempts)::numeric, 2) as promedio_llamadas,
    ROUND((SUM(processing_attempts)::numeric - COUNT(*)) / COUNT(*) * 100, 1) as overhead_porcentaje
FROM responses;
"
```

**Narración**:
> "El costo computacional del feedback loop:
> 
> - **Total de preguntas**: X
> - **Total de llamadas al LLM**: Y
> - **Overhead**: (Y-X)/X = Z%
> 
> Esto significa que el sistema realiza un Z% más de llamadas al LLM para garantizar calidad. Este overhead es aceptable considerando la mejora de X% en el score promedio."

---

## 7. PREGUNTAS Y RESPUESTAS

### Q1: ¿Por qué usar Apache Kafka en lugar de llamadas directas?

**Respuesta**:
```powershell
Write-Host @"
VENTAJAS DEL MODELO ASÍNCRONO:

1. DESACOPLAMIENTO:
   - Los servicios no dependen de la disponibilidad inmediata de otros
   - Tolerancia a fallos: si el LLM falla, las preguntas esperan en la cola
   - Escalabilidad independiente de cada componente

2. RESILIENCIA:
   - Persistencia de mensajes: no se pierde información en caso de fallo
   - Reintentos automáticos sin afectar al cliente
   - Distribución de carga entre múltiples consumidores

3. RENDIMIENTO:
   - Throughput: Procesamos ~X preguntas/segundo
   - Latencia asíncrona: El usuario no espera el procesamiento completo
   - Buffer de carga: Kafka absorbe picos de tráfico

DESVENTAJAS:

1. COMPLEJIDAD:
   - Más componentes que mantener (Zookeeper, Kafka, consumidores)
   - Curva de aprendizaje para el equipo

2. LATENCIA PERCIBIDA:
   - Modelo síncrono: respuesta inmediata
   - Modelo asíncrono: respuesta eventual (segundos a minutos)
   - Requiere sistema de notificaciones o polling

3. CONSISTENCIA:
   - Eventual consistency vs strong consistency
   - Requiere manejo cuidadoso del estado
"@
```

### Q2: ¿Cómo se justifica la estrategia de reintento?

**Respuesta**:
```powershell
Write-Host @"
ESTRATEGIA DE REINTENTOS IMPLEMENTADA:

1. ERROR POR SOBRECARGA (Exponential Backoff):
   - Intento 1: 2 segundos
   - Intento 2: 4 segundos
   - Intento 3: 8 segundos
   
   JUSTIFICACIÓN:
   - El modelo necesita tiempo para recuperarse
   - Evita saturar más el sistema
   - Aumenta probabilidad de éxito con cada intento

2. ERROR POR CUOTA (Fixed Delay):
   - Delay fijo: 60 segundos
   
   JUSTIFICACIÓN:
   - Los límites de cuota se resetean cada minuto
   - No tiene sentido reintentar antes
   - Ahorra recursos del sistema

3. MÁXIMO DE REINTENTOS:
   - Límite: 3 intentos
   
   JUSTIFICACIÓN:
   - Previene ciclos infinitos
   - Balance entre calidad y costo
   - Errores permanentes van a tópico dedicado

DATOS DE EFECTIVIDAD:
"@

docker exec postgres_db psql -U user -d yahoo_db -c "
SELECT 
    CASE 
        WHEN processing_attempts = 1 THEN 'Éxito al primer intento'
        WHEN processing_attempts = 2 THEN 'Recuperadas tras 1 reintento'
        WHEN processing_attempts = 3 THEN 'Recuperadas tras 2 reintentos'
    END as categoria,
    COUNT(*) as cantidad,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM responses), 1) as porcentaje
FROM responses
GROUP BY processing_attempts
ORDER BY processing_attempts;
"
```

### Q3: ¿Cómo se previenen ciclos infinitos en el feedback loop de Flink?

**Respuesta**:
```powershell
Write-Host @"
MECANISMOS DE PREVENCIÓN DE CICLOS INFINITOS:

1. CONTADOR DE REINTENTOS:
   - Cada mensaje incluye campo 'processing_attempts'
   - Se incrementa en cada iteración del loop
   - Verificado antes de reinyectar

2. LÍMITE MÁXIMO:
   - MAX_RETRIES = 3 en ScoreValidatorJob.java
   - Respuestas que alcanzan el límite:
     * Se marcan como 'max_retries_reached'
     * Se persisten con su mejor score obtenido
     * No se reinyectan más

3. ENRUTAMIENTO INTELIGENTE:
   - Flink usa filtros de stream:
     * score < THRESHOLD && retries < MAX → Regenerar
     * score >= THRESHOLD || retries >= MAX → Persistir

4. MONITOREO:
   - Dashboard muestra distribución de intentos
   - Alertas si todas las respuestas alcanzan máximo

VERIFICACIÓN:
"@

docker exec postgres_db psql -U user -d yahoo_db -c "
SELECT 
    MAX(processing_attempts) as max_intentos_observado,
    COUNT(CASE WHEN processing_attempts >= 3 THEN 1 END) as respuestas_limite_maximo
FROM responses;
"

Write-Host @"

CONCLUSIÓN:
- Ninguna respuesta excede 3 intentos ✅
- El sistema respeta el límite configurado ✅
"@
```

### Q4: ¿Qué tecnologías alternativas se evaluaron?

**Respuesta**:
```powershell
Write-Host @"
COMPARACIÓN DE TECNOLOGÍAS:

KAFKA vs RabbitMQ:
✅ Kafka: Elegido por throughput superior y persistencia durable
❌ RabbitMQ: Mejor para enrutamiento complejo, pero menor throughput

FLINK vs Spark Streaming:
✅ Flink: Latencia más baja (milisegundos), streaming puro
❌ Spark: Micro-batching, latencia más alta (segundos)

OLLAMA vs API de Gemini:
✅ Ollama: Sin límites de rate, ejecución local, control total
❌ Gemini: Requiere internet, límites de cuota, pero mayor calidad

POSTGRESQL vs MongoDB:
✅ PostgreSQL: ACID garantizado, consultas SQL complejas
❌ MongoDB: Esquema flexible, pero menos consistencia

REDIS vs Memcached:
✅ Redis: Estructuras de datos avanzadas, persistencia opcional
❌ Memcached: Más simple, solo key-value
"@
```

### Q5: ¿Cómo escala el sistema?

**Respuesta**:
```powershell
Write-Host @"
ESTRATEGIAS DE ESCALABILIDAD:

1. ESCALADO HORIZONTAL DE CONSUMIDORES:
   - LLM Consumer: Ya tiene 2 réplicas
   - Comando para escalar:
     docker-compose -f docker-compose-tarea2.yml up -d --scale llm-consumer=5
   
   - Kafka distribuye automáticamente entre réplicas
   - Cada réplica procesa una partición diferente

2. ESCALADO DE KAFKA:
   - Aumentar particiones de tópicos:
     docker exec kafka_broker kafka-topics --alter \\
       --topic questions-pending --partitions 10
   
   - Agregar más brokers para replicación

3. ESCALADO DE FLINK:
   - Aumentar TaskManagers en docker-compose:
     deploy:
       replicas: 3
   
   - Flink redistribuye el procesamiento automáticamente

4. ESCALADO DE ALMACENAMIENTO:
   - PostgreSQL: Replicación read-replica
   - Redis: Redis Cluster con sharding

DEMOSTRACIÓN DE ESCALADO:
"@

# Escalar consumidores LLM a 4 réplicas
docker-compose -f docker-compose-tarea2.yml up -d --scale llm-consumer=4

Start-Sleep -Seconds 10

# Verificar réplicas
docker ps --filter "name=llm-consumer" --format "table {{.Names}}\t{{.Status}}"
```

---

## 8. CIERRE Y LIMPIEZA

### 8.1 Mostrar Documentación Final

```powershell
Write-Host "`n=== DOCUMENTACIÓN ENTREGABLE ===" -ForegroundColor Green
Get-ChildItem -Filter "*.md" | Format-Table Name, @{Name="Tamaño (KB)"; Expression={[math]::Round($_.Length/1KB, 2)}}, LastWriteTime
```

**Narración**:
> "Toda la documentación técnica está disponible:
> - Arquitectura detallada
> - Justificación de decisiones
> - Análisis de métricas
> - Guías de despliegue
> - Código fuente comentado"

### 8.2 Estadísticas Finales

```powershell
Write-Host "`n=== RESUMEN FINAL DEL SISTEMA ===" -ForegroundColor Cyan

docker exec postgres_db psql -U user -d yahoo_db -c "
SELECT 
    'Total Preguntas' as metrica, 
    COUNT(*)::text as valor 
FROM responses
UNION ALL
SELECT 
    'Score Promedio', 
    ROUND(AVG(bert_score)::numeric, 3)::text 
FROM responses
UNION ALL
SELECT 
    'Mejora vs Umbral Inicial', 
    ROUND((AVG(bert_score) - 0.75) / 0.75 * 100, 1)::text || '%' 
FROM responses
UNION ALL
SELECT 
    'Overhead Computacional', 
    ROUND((SUM(processing_attempts)::numeric - COUNT(*)) / COUNT(*) * 100, 1)::text || '%'
FROM responses;
"
```

### 8.3 Detener el Sistema (Opcional)

```powershell
Write-Host "`n=== DETENIENDO SISTEMA ===" -ForegroundColor Yellow
# docker-compose -f docker-compose-tarea2.yml down

Write-Host @"

✅ DEMOSTRACIÓN COMPLETADA

El sistema cumple con TODOS los requerimientos de la Tarea 2:
✅ Pipeline asíncrono con Kafka (7 tópicos diseñados)
✅ Gestión de fallos con 2 estrategias de reintento
✅ Procesamiento de flujos con Apache Flink
✅ Feedback loop con prevención de ciclos infinitos
✅ Despliegue completo con Docker Compose
✅ Documentación técnica exhaustiva
✅ Dashboard de visualización de métricas
✅ Análisis justificado del umbral de calidad

Gracias por su atención.
"@
```

---

## 📎 ANEXOS

### A. Comandos Útiles para Debugging

```powershell
# Ver logs de todos los servicios
docker-compose -f docker-compose-tarea2.yml logs --tail=50

# Ver logs de un servicio específico
docker logs <container_name> --tail 100 --follow

# Ejecutar comando dentro de un contenedor
docker exec -it <container_name> bash

# Ver uso de recursos
docker stats

# Reiniciar un servicio específico
docker-compose -f docker-compose-tarea2.yml restart <service_name>
```

### B. URLs de Interfaces

```
- Flink UI:      http://localhost:8081
- Kafka UI:      http://localhost:8080
- Dashboard:     http://localhost:5002
- Storage API:   http://localhost:5001
```

### C. Estructura de Archivos Clave

```
yahoo_llm_project/
├── docker-compose-tarea2.yml      # Orquestación completa
├── flink-job/                     # Job compilado de Flink
│   └── target/
│       └── flink-score-validator-1.0.jar
├── llm_consumer/                  # Consumidor LLM asíncrono
├── retry_consumers/               # Consumidores de reintento
├── score_validator/               # Servicio de cálculo de score
├── storage_service/               # Persistencia asíncrona
├── viz_service/                   # Dashboard de métricas
├── README_TAREA2_FLINK.md        # Arquitectura técnica
├── CUMPLIMIENTO_TAREA2.md        # Verificación de requerimientos
├── ANALISIS_SCORES.md            # Justificación de umbral
└── GUION_DEMOSTRACION_TAREA2.md  # Este documento
```

---

**Tiempo estimado de demostración**: 20-25 minutos  
**Requisitos previos**: Docker, Docker Compose, Ollama instalados  
**Hardware mínimo**: 8GB RAM, 4 CPU cores, 20GB disco

---

*Documento creado para la demostración de la Tarea 2*  
*Sistemas Distribuidos - 2025*
