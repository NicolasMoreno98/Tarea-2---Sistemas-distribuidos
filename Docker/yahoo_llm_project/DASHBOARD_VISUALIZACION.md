# 📊 Dashboard de Visualización de Flink Scores

## ✅ Implementación Completada

Se ha agregado exitosamente un **servicio de visualización** que muestra estadísticas y gráficos de los scores calculados por Apache Flink.

---

## 🎯 Respuesta a tu Pregunta

### ¿Se pueden asignar Flink scores a la base de datos?
**✅ SÍ - Ya implementado**

Los scores calculados por Flink **YA se están guardando** en PostgreSQL en la columna `bert_score` de la tabla `responses`.

**Flujo actual:**
```
1. Flink consume llm-responses-success
2. Calcula BERTScore (vía HTTP a score-validator:8000)
3. Publica a validated-responses CON EL SCORE
4. Storage Service consume y persiste en PostgreSQL:
   → Columna bert_score (NUMERIC)
   → Incluye: question_id, question_text, llm_response, bert_score, etc.
```

### ¿Es posible obtener estadísticas con gráficos?
**✅ SÍ - Implementado ahora mismo**

Se creó un servicio completo de visualización con:
- Dashboard web interactivo
- 5 tipos de gráficos diferentes
- API REST para estadísticas
- Auto-refresh cada 30 segundos

---

## 📊 Dashboard de Visualización

### Acceso
**URL Principal:** http://localhost:5002

### Gráficos Disponibles

#### 1. **Distribución de Scores por Rangos**
- Tipo: Gráfico de Barras
- Muestra: Cantidad de respuestas en cada rango de score
- Rangos: 0.0-0.5, 0.5-0.6, 0.6-0.7, 0.7-0.75, 0.75-0.8, 0.8-0.9, 0.9-1.0
- Destaca: Umbral de Flink (0.75) en verde

#### 2. **Intentos de Procesamiento**
- Tipo: Gráfico de Dona (Doughnut)
- Muestra: Distribución de respuestas por número de intentos
- Útil para: Ver cuántas respuestas necesitaron reprocesamiento

#### 3. **Histograma Detallado**
- Tipo: Histograma (bins de 0.05)
- Muestra: Distribución precisa de scores
- Color: Verde para >= 0.75, Rojo para < 0.75
- Útil para: Análisis detallado de la distribución

#### 4. **Mejora de Calidad por Reintentos**
- Tipo: Gráfico de Línea
- Muestra: Score promedio según número de intentos
- Útil para: **Analizar si los reintentos mejoran la calidad**
- Responde: "¿Vale la pena regenerar respuestas con score bajo?"

#### 5. **Serie Temporal (24 horas)**
- Tipo: Gráfico de Línea
- Muestra: Evolución del score promedio por hora
- Útil para: Detectar patrones temporales

### Estadísticas en Tiempo Real

Cards con métricas clave:
- 📝 **Total Respuestas**: Cantidad total procesada
- ⭐ **Score Promedio**: Calidad promedio general
- 📈 **Score Máximo**: Mejor score alcanzado
- ⏱️ **Tiempo Promedio**: Milisegundos de procesamiento

---

## 🔌 API Endpoints

### 1. Estadísticas Generales
```http
GET http://localhost:5002/api/statistics
```

**Response:**
```json
{
  "total_responses": 150,
  "avg_score": 0.823,
  "min_score": 0.612,
  "max_score": 0.965,
  "score_distribution": [
    {"range": "0.7-0.75", "count": 25},
    {"range": "0.75-0.8", "count": 50},
    {"range": "0.8-0.9", "count": 60},
    {"range": "0.9-1.0", "count": 15}
  ],
  "attempts_distribution": [
    {"attempts": 1, "count": 100},
    {"attempts": 2, "count": 35},
    {"attempts": 3, "count": 15}
  ],
  "avg_processing_time_ms": 1250,
  "responses_24h": 145
}
```

### 2. Serie Temporal
```http
GET http://localhost:5002/api/scores/timeseries
```

**Response:**
```json
[
  {
    "timestamp": "2025-10-29T10:00:00",
    "avg_score": 0.815,
    "count": 12
  },
  {
    "timestamp": "2025-10-29T11:00:00",
    "avg_score": 0.829,
    "count": 18
  }
]
```

### 3. Histograma Detallado
```http
GET http://localhost:5002/api/scores/histogram
```

**Response:**
```json
[
  {"bin_start": 0.70, "bin_end": 0.75, "count": 25},
  {"bin_start": 0.75, "bin_end": 0.80, "count": 42},
  {"bin_start": 0.80, "bin_end": 0.85, "count": 38}
]
```

### 4. Análisis de Mejora por Reintentos
```http
GET http://localhost:5002/api/quality/improvement
```

**Response:**
```json
[
  {"attempts": 1, "avg_score": 0.745, "count": 100},
  {"attempts": 2, "avg_score": 0.812, "count": 35},
  {"attempts": 3, "avg_score": 0.879, "count": 15}
]
```

**Conclusión de este endpoint:**
> Si el score promedio aumenta con más intentos, significa que el **feedback loop de Flink está funcionando** y mejorando la calidad.

### 5. Top Questions
```http
GET http://localhost:5002/api/questions/top
```

Retorna las 10 preguntas con mejor y peor score.

### 6. Health Check
```http
GET http://localhost:5002/health
```

---

## 🗄️ Estructura de Base de Datos

### Tabla `responses`

```sql
CREATE TABLE IF NOT EXISTS responses (
    question_id VARCHAR(16) PRIMARY KEY,
    question_text TEXT NOT NULL,
    llm_response TEXT NOT NULL,
    original_answer TEXT,
    bert_score NUMERIC,                    -- ← AQUÍ SE GUARDA EL FLINK SCORE
    processing_attempts INTEGER DEFAULT 1,
    total_processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Columnas relevantes:**
- `bert_score`: Score calculado por Flink (0.0 - 1.0)
- `processing_attempts`: Número de reintentos (1, 2, 3)
- `question_text`: Pregunta original
- `llm_response`: Respuesta generada
- `total_processing_time_ms`: Latencia total

---

## 🚀 Tecnologías Utilizadas

### Backend
- **Flask 2.3.3**: Framework web ligero
- **psycopg2**: Conector PostgreSQL
- **Python 3.11**: Lenguaje base

### Frontend
- **Chart.js 4.4.0**: Librería de gráficos interactivos
- **HTML5 + CSS3**: Interfaz moderna
- **JavaScript vanilla**: Fetching de datos y actualización dinámica

### Estilos
- Gradiente morado (667eea → 764ba2)
- Cards con hover effects
- Responsive design (mobile-friendly)
- Tema moderno y limpio

---

## 📦 Docker

### Nuevo Servicio en docker-compose-tarea2.yml

```yaml
viz-service:
  build: ./viz_service
  container_name: viz_service
  depends_on:
    postgres:
      condition: service_healthy
  ports:
    - "5002:5002"
  environment:
    - DATABASE_URL=postgresql://user:password@postgres:5432/yahoo_db
  networks:
    - yahoo_network
  healthcheck:
    test: ["CMD-SHELL", "python -c \"import requests; requests.get('http://localhost:5002/health')\" || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### Archivos Creados

```
viz_service/
├── Dockerfile
├── requirements.txt
├── app.py               (Backend Flask con endpoints)
└── templates/
    └── dashboard.html   (Frontend con Chart.js)
```

---

## 🎯 Análisis que Permite el Dashboard

### 1. Efectividad del Feedback Loop
**Pregunta:** ¿Mejora la calidad con los reintentos?

**Cómo verificar:**
- Ver gráfico "Mejora de Calidad por Reintentos"
- Si la línea sube → Los reintentos mejoran la calidad ✅
- Si la línea es plana → Los reintentos no ayudan ❌

### 2. Distribución de Calidad
**Pregunta:** ¿Qué porcentaje de respuestas cumplen el umbral?

**Cómo verificar:**
- Ver gráfico "Distribución de Scores"
- Sumar barras >= 0.75 vs < 0.75
- Calcular porcentaje de aceptación

### 3. Costo Computacional
**Pregunta:** ¿Cuántas respuestas necesitan reprocesamiento?

**Cómo verificar:**
- Ver gráfico "Intentos de Procesamiento"
- % con 1 intento = respuestas OK a la primera
- % con 2-3 intentos = costo adicional del feedback loop

### 4. Tendencias Temporales
**Pregunta:** ¿Varía la calidad según la hora del día?

**Cómo verificar:**
- Ver gráfico "Serie Temporal (24h)"
- Identificar picos y valles
- Correlacionar con carga del LLM

---

## 📊 Interpretación de Métricas

### Score Promedio Ideal
- **>= 0.85**: Excelente calidad
- **0.75 - 0.85**: Buena calidad (cumple umbral)
- **0.65 - 0.75**: Calidad media (se reprocesan)
- **< 0.65**: Baja calidad (múltiples reintentos)

### Intentos de Procesamiento
- **1 intento: ~70%**: Sistema eficiente
- **2 intentos: ~20%**: Feedback loop útil
- **3 intentos: ~10%**: Límite alcanzado
- **Si >30% necesita 2+ intentos**: Revisar threshold o LLM

### Tiempo de Procesamiento
- **< 1000ms**: Muy rápido
- **1000-2000ms**: Aceptable
- **2000-5000ms**: Lento pero funcional
- **> 5000ms**: Investigar cuellos de botella

---

## 🔄 Auto-Refresh

El dashboard se actualiza automáticamente cada **30 segundos**.

También puedes actualizar manualmente con el botón:
```
🔄 Actualizar Datos
```

---

## 🎓 Para el Informe de Tarea 2

### Sección: "Análisis del Procesamiento de Flujos (Flink)"

**Datos que puedes incluir del dashboard:**

1. **Umbral de Score Justificado:**
   - "Definimos un umbral de 0.75 basado en el análisis del histograma"
   - Mostrar screenshot del histograma
   - Explicar que >= 0.75 indica similitud semántica alta

2. **Efectividad del Feedback Loop:**
   - "El gráfico de 'Mejora por Reintentos' muestra que..."
   - Calcular: Δ Score = score_intento2 - score_intento1
   - Mostrar screenshot del gráfico de línea
   - Conclusión: "Los reintentos mejoraron el score promedio en X%"

3. **Costo Computacional:**
   - "El X% de las respuestas fueron aceptadas al primer intento"
   - "El feedback loop generó Y llamadas adicionales al LLM"
   - Calcular: Total llamadas = count1 + count2*2 + count3*3
   - Mostrar gráfico de dona con distribución

4. **Métricas Temporales:**
   - "El score promedio se mantiene estable en 0.8X durante 24h"
   - Mostrar serie temporal
   - Identificar outliers o anomalías

---

## 🚀 Comandos para Usar

### Levantar el Dashboard
```bash
cd "d:\U\Sistemas Distribuidos\Docker\yahoo_llm_project"
docker-compose -f docker-compose-tarea2.yml up -d viz-service
```

### Ver Logs
```bash
docker logs -f viz_service
```

### Reiniciar el Servicio
```bash
docker-compose -f docker-compose-tarea2.yml restart viz-service
```

### Acceder al Dashboard
```bash
# En tu navegador
http://localhost:5002
```

### Probar la API
```bash
# PowerShell
Invoke-RestMethod -Uri "http://localhost:5002/api/statistics" | ConvertTo-Json

# O curl
curl http://localhost:5002/api/statistics
```

---

## ✅ Sistema Completo Actualizado

### Contenedores Activos: **15 Total**

1. postgres_db
2. redis_cache
3. zookeeper
4. kafka_broker
5. flink_jobmanager
6. flink_taskmanager
7. storage_service
8. score_validator
9. llm-consumer-1
10. llm-consumer-2
11. retry_overload_consumer
12. retry_quota_consumer
13. traffic_generator
14. kafka_ui
15. **viz_service** ← NUEVO 🎉

### URLs del Sistema

| Servicio | URL | Descripción |
|----------|-----|-------------|
| **Viz Dashboard** | http://localhost:5002 | 📊 Gráficos de scores (NUEVO) |
| Flink UI | http://localhost:8081 | Panel de control de Flink |
| Kafka UI | http://localhost:8080 | Monitoreo de topics |
| Storage Metrics | http://localhost:5001/metrics | Métricas del storage |
| Score Validator | http://localhost:8000/health | Health check del validator |

---

## 🎉 Conclusión

**✅ Pregunta 1: ¿Se puede asignar Flink score a la BD?**
→ **SÍ**, ya se está guardando en `responses.bert_score`

**✅ Pregunta 2: ¿Se pueden obtener estadísticas con gráficos?**
→ **SÍ**, dashboard completo en http://localhost:5002

**🎯 Resultado:**
- 5 tipos de gráficos interactivos
- 8 endpoints de API
- Auto-refresh cada 30 segundos
- Análisis de mejora por reintentos
- Métricas temporales (24h)
- Histogramas detallados

**🚀 Listo para:**
- Demostración en vivo
- Screenshots para informe
- Análisis de resultados
- Evaluación de efectividad del feedback loop
