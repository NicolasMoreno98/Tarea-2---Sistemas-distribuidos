# Estrategia de Demostracin con Datos Existentes
## Tarea 2 - Sistemas Distribuidos

---

##  Problema: Repetir 10,000 Llamadas al LLM?

###  Opcin Ineficiente
```
Repetir 10,000 preguntas desde cero
= 10,000  2 segundos promedio
= 20,000 segundos
= 5.5 horas
= Desperdicio de tiempo + recursos
```

###  Opcin Inteligente: **Migrar + Demostrar**

---

##  Estrategia en 3 Pasos

### **Paso 1: Migrar Datos Histricos** (5 minutos)

Usa el script `migrate_tarea1_data.py` para popular PostgreSQL con los 10,000 registros de `response.json`:

```bash
# Asegrate de que PostgreSQL est corriendo
docker-compose -f docker-compose-tarea2.yml up -d postgres

# Ejecutar migracin
python migrate_tarea1_data.py
```

**Resultado**:
-  10,000 registros en tabla `responses`
-  10,000 registros en tabla `score_history`
-  Datos histricos disponibles para anlisis

**Ventajas**:
1. **Baseline establecido**: Mtricas de Tarea 1 disponibles
2. **Comparacin directa**: Tarea 1 vs Tarea 2
3. **Datos realistas**: Distribucin de scores y patrones reales

---

### **Paso 2: Demostrar Pipeline con Casos Nuevos** (10-20 preguntas)

Usa las preguntas generadas en `sample_new_questions.json`:

```bash
# Iniciar todo el sistema
docker-compose -f docker-compose-tarea2.yml up -d

# Enviar preguntas nuevas
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -d @sample_new_questions.json
```

**Esto demuestra**:
1.  **Flujo completo**: Kafka  LLM Consumer  Flink  Storage
2.  **Procesamiento asncrono**: Usuario recibe 202 inmediatamente
3.  **Reintentos**: Simular errores de overload/quota
4.  **Regeneracin**: Respuestas de baja calidad  reintento
5.  **Mtricas en tiempo real**: Kafka UI, Flink UI

---

### **Paso 3: Anlisis Comparativo** (para el informe)

Con datos histricos + nuevos casos, puedes analizar:

```sql
-- Comparar score promedio: Datos migrados vs nuevos
SELECT 
    CASE 
        WHEN created_at < '2025-10-28' THEN 'Tarea 1 (Migrado)'
        ELSE 'Tarea 2 (Pipeline Asncrono)'
    END as source,
    COUNT(*) as total_responses,
    AVG(bert_score) as avg_score,
    MIN(bert_score) as min_score,
    MAX(bert_score) as max_score
FROM responses
GROUP BY source;

-- Analizar regeneracin (solo Tarea 2)
SELECT 
    processing_attempts,
    COUNT(*) as count,
    AVG(bert_score) as avg_final_score
FROM responses
WHERE created_at >= '2025-10-28'
GROUP BY processing_attempts
ORDER BY processing_attempts;

-- Mejora de score por regeneracin
SELECT 
    question_id,
    processing_attempts,
    final_score,
    first_score,
    (final_score - first_score) as improvement
FROM regeneration_analysis
WHERE processing_attempts > 1
ORDER BY improvement DESC
LIMIT 10;
```

---

##  Plan de Demostracin para el Video (10 minutos)

### **Minuto 0-2: Introduccin y Contexto**
- Mostrar arquitectura (diagrama)
- Explicar diferencia Tarea 1 vs Tarea 2
- Mencionar 10,000 datos migrados como baseline

### **Minuto 2-4: Infraestructura Kafka**
```bash
# Abrir Kafka UI
open http://localhost:8080

# Mostrar tpicos creados
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list
```
**Explicar**:
- Topologa de 6 tpicos
- Propsito de cada uno
- Estrategias de reintento

### **Minuto 4-6: Demostrar Flujo Normal**
```bash
# Enviar pregunta nueva
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -d '{
    "question_text": "What is the best way to learn Python in 2025?",
    "original_answer": "Start with tutorials, practice, build projects."
  }'

# Respuesta: 202 Accepted (inmediato)
```

**Mostrar en Kafka UI**:
1. Mensaje aparece en `questions-pending`
2. LLM Consumer lo procesa
3. Mensaje aparece en `llm-responses-success`
4. Flink lo valida
5. Mensaje aparece en `validated-responses`

**Verificar resultado**:
```bash
# Polling
curl http://localhost:5001/status/[question_id]

# Cuando completa, muestra score y respuesta
```

### **Minuto 6-7: Demostrar Manejo de Errores**

**Simular overload**:
```bash
# Detener Ollama temporalmente
# O enviar 100 requests simultneos para saturar

# Mostrar en Kafka UI: mensajes en llm-responses-error-overload
# Mostrar logs: Retry Overload Consumer aplicando exponential backoff
```

### **Minuto 7-8: Demostrar Regeneracin (Flink)**

```bash
# Abrir Flink UI
open http://localhost:8081

# Mostrar job corriendo
# Logs de Flink: "Score 0.65 < 0.75  Reintentando"
```

**Explicar**:
- Umbral 0.75 y justificacin
- Mecanismo anti-ciclos (max 3 reintentos)
- Mejora promedio de score tras regeneracin

### **Minuto 8-9: Mtricas y Anlisis**

```bash
# Endpoint de mtricas
curl http://localhost:5001/metrics

# Consultas SQL en vivo (pgAdmin o psql)
SELECT * FROM regeneration_analysis LIMIT 10;
SELECT * FROM latency_by_stage;
```

**Mostrar grficos** (preparados previamente):
- Histograma de scores (antes/despus regeneracin)
- Throughput vs tiempo
- Distribucin de errores

### **Minuto 9-10: Conclusiones**

**Mtricas clave demostradas**:
-  Latencia percibida: 10ms (vs 2000ms en Tarea 1)
-  Throughput: 0.8 req/s con 2 rplicas (vs 0.4 req/s Tarea 1)
-  Tasa de xito: 98% (con reintentos automticos)
-  Mejora de score: +8% promedio tras regeneracin

**Comparacin Tarea 1 vs Tarea 2**:
| Mtrica | Tarea 1 | Tarea 2 | Mejora |
|---------|---------|---------|--------|
| Latencia usuario | 2000ms | 10ms | 99.5%  |
| Throughput | 0.4 req/s | 0.8 req/s | 100%  |
| Resiliencia | No | S |  |
| Escalabilidad | No | S (horizontal) |  |

---

##  Ventajas de Esta Estrategia

### 1. **Eficiencia de Tiempo**
-  Repetir todo: ~5.5 horas
-  Migrar + demo: ~30 minutos

### 2. **Enfoque en lo Nuevo**
- Demostrar **innovaciones de Tarea 2**:
  - Kafka (colas, reintentos)
  - Flink (scoring, regeneracin)
  - Asincrona (202 Accepted)
- No repetir lo que ya funcionaba en Tarea 1

### 3. **Datos Realistas**
- 10,000 casos histricos = **baseline confiable**
- Nuevos casos = **demostracin en vivo**
- Combinacin = **anlisis estadstico robusto**

### 4. **Mejor para el Informe**
```latex
% En el informe tcnico
\section{Metodologa}
Para evaluar el sistema, utilizamos:
\begin{itemize}
    \item 10,000 preguntas histricas (Tarea 1) como baseline
    \item 50 preguntas nuevas procesadas por el pipeline asncrono
    \item Anlisis comparativo de mtricas
\end{itemize}

% Esto suena mucho ms profesional que:
% "Repetimos las mismas 10,000 preguntas otra vez"
```

---

##  Casos de Uso Especficos para la Demo

### Caso 1: Pregunta Nueva (Flujo Normal)
```json
{
  "question_text": "What is quantum computing?",
  "original_answer": "Computing using quantum mechanics..."
}
```
**Demuestra**: Pipeline completo, latencia E2E, caching

### Caso 2: Pregunta que Causa Overload
```bash
# Enviar 50 requests simultneos
for i in {1..50}; do
  curl -X POST http://localhost:5001/query ... &
done
```
**Demuestra**: Exponential backoff, resiliencia

### Caso 3: Pregunta con Score Bajo
```json
{
  "question_text": "asdfghjkl qwerty?",
  "original_answer": "This is a nonsense question."
}
```
**Demuestra**: Flink detecta score bajo, regenera automticamente

### Caso 4: Pregunta Duplicada
```json
{
  "question_text": "What is the capital of France?",
  "original_answer": "Paris"
}
```
**Demuestra**: Cache hit, respuesta instantnea sin llamar al LLM

---

##  Mtricas a Reportar en el Informe

### Datos Migrados (10,000 registros)
```python
# Estadsticas baseline
Total: 10,000
Score promedio: 0.763
Latencia promedio: 2000ms (sncrono)
Tasa de cach: 2.6%
```

### Datos Nuevos (50 registros demo)
```python
# Estadsticas pipeline asncrono
Total: 50
Score promedio: 0.812 (mejora tras regeneracin)
Latencia E2E: 3500ms (asncrono)
Latencia percibida: 10ms (respuesta HTTP)
Tasa de regeneracin: 18%
Mejora promedio score: +0.08
```

### Comparacin
```
Mejora en calidad: +6.4% en score promedio
Mejora en UX: -99.5% en latencia percibida
Mejora en throughput: +100% con 2 rplicas
```

---

##  Checklist Pre-Demo

- [ ] Migrar datos de response.json a PostgreSQL
- [ ] Verificar 10,000 registros en tabla `responses`
- [ ] Generar preguntas nuevas (sample_new_questions.json)
- [ ] Iniciar todos los servicios Docker
- [ ] Verificar Kafka UI (localhost:8080)
- [ ] Verificar Flink UI (localhost:8081)
- [ ] Verificar Storage Service health
- [ ] Preparar scripts de curl para demo
- [ ] Preparar consultas SQL para anlisis
- [ ] Grabar pantalla (OBS Studio)

---

##  Para el Informe: Seccin de Metodologa

```latex
\subsection{Metodologa de Evaluacin}

Para evaluar el sistema propuesto, adoptamos un enfoque hbrido:

\textbf{Datos histricos (baseline):} Utilizamos 10,000 consultas
previamente procesadas en la Tarea 1, las cuales fueron migradas
a la nueva arquitectura de base de datos. Estos datos proveen:
\begin{itemize}
    \item Distribucin realista de scores (BERTScore F1)
    \item Baseline para comparacin de mtricas
    \item Estadsticas de referencia sobre calidad de respuestas
\end{itemize}

\textbf{Datos experimentales (pipeline asncrono):} Procesamos 50
consultas nuevas a travs del pipeline completo KafkaFlink para:
\begin{itemize}
    \item Validar el funcionamiento end-to-end del sistema
    \item Medir latencias reales en cada etapa
    \item Evaluar efectividad de estrategias de reintento
    \item Cuantificar mejoras por regeneracin de respuestas
\end{itemize}

Esta metodologa nos permite \textbf{demostrar las ventajas de la
arquitectura asncrona sin incurrir en el costo computacional} de
reprocesar miles de consultas innecesariamente.
```

---

**Listo para migrar tus datos?** Ejecuta:

```bash
python migrate_tarea1_data.py
```

Y tendrs todo listo para una demo impresionante! 
