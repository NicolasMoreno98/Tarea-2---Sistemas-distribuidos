# Flink Score Validator Job

## 📝 Descripción

Job de Apache Flink que procesa el flujo de respuestas del LLM para validar su calidad mediante BERTScore y decidir si regenerar o persistir cada respuesta.

## 🏗️ Arquitectura

```
Kafka Topic: llm-responses-success
         ↓
    [Flink Job]
         ↓
    Calculate BERTScore
         ↓
    Decision Logic
    ↙          ↘
Score < 0.75   Score ≥ 0.75
     ↓              ↓
questions-pending  validated-responses
(regenerar)        (persistir)
```

## 🎯 Funcionalidad

1. **Consume** respuestas exitosas desde `llm-responses-success`
2. **Calcula** BERTScore comparando respuesta LLM vs respuesta original
3. **Decide** basado en umbral de calidad (0.75):
   - **Baja calidad** (< 0.75): Reinyecta a `questions-pending` para regeneración
   - **Alta calidad** (≥ 0.75): Publica a `validated-responses` para persistencia
4. **Previene ciclos infinitos**: Máximo 3 reintentos por pregunta

## 🔧 Requisitos

- Java 11+
- Maven 3.6+
- Docker con Flink 1.18
- Kafka corriendo en puerto 9092

## 📦 Compilación

### Opción 1: Maven Local

```bash
cd flink-job
mvn clean package
```

Genera: `target/flink-score-validator-1.0.jar`

### Opción 2: Docker Build

```bash
docker build -t flink-job-builder .
```

## 🚀 Despliegue

### Método 1: Script Automático (Recomendado)

**PowerShell:**
```powershell
cd flink-job
.\deploy-job.ps1
```

**Bash:**
```bash
cd flink-job
chmod +x deploy-job.sh
./deploy-job.sh
```

### Método 2: Manual

1. Compilar el JAR:
```bash
mvn clean package -DskipTests
```

2. Copiar JAR al contenedor:
```bash
docker cp target/flink-score-validator-1.0.jar flink_jobmanager:/opt/flink-job/
```

3. Desplegar en Flink:
```bash
docker exec flink_jobmanager flink run -d /opt/flink-job/flink-score-validator-1.0.jar
```

## 🖥️ Monitoreo

**Flink Web UI:** http://localhost:8081

Desde la UI puedes:
- Ver el job ejecutándose
- Monitorear métricas (throughput, latencia)
- Ver logs de ejecución
- Cancelar/reiniciar el job

## 📊 Logs

Ver logs del job en tiempo real:

```bash
# Logs de JobManager
docker logs -f flink_jobmanager

# Logs de TaskManager
docker logs -f flink_taskmanager
```

## ⚙️ Configuración

Variables de entorno en `docker-compose-tarea2.yml`:

```yaml
environment:
  - KAFKA_BROKER=kafka:9092              # Broker de Kafka
  - JOB_MANAGER_RPC_ADDRESS=flink-jobmanager  # Dirección del JobManager
```

Constantes en `ScoreValidatorJob.java`:

```java
private static final double QUALITY_THRESHOLD = 0.75;  // Umbral de calidad
private static final int MAX_RETRIES = 3;              // Máximo reintentos
```

## 🔍 Verificación

1. **Job desplegado:**
```bash
docker exec flink_jobmanager flink list
```

2. **Kafka topics activos:**
```bash
docker exec kafka_broker kafka-topics --list --bootstrap-server localhost:9092
```

3. **Mensajes procesados:**
Acceder a Kafka UI: http://localhost:8080

## 🐛 Troubleshooting

### Job no se despliega

```bash
# Verificar que Flink esté corriendo
docker ps | grep flink

# Verificar logs de error
docker logs flink_jobmanager
```

### Error de conexión a Kafka

```bash
# Verificar que Kafka esté saludable
docker ps | grep kafka
docker exec kafka_broker kafka-broker-api-versions --bootstrap-server localhost:9092
```

### Job se detiene inesperadamente

```bash
# Ver logs detallados
docker exec flink_jobmanager cat /opt/flink/log/flink-*-jobmanager-*.log
```

## 📚 Dependencias Maven

- **Flink Streaming:** 1.18.0
- **Flink Kafka Connector:** 3.0.1-1.18
- **Jackson (JSON):** 2.15.2
- **Apache HttpClient:** 5.2.1

## 🏆 Cumplimiento de Requerimientos

✅ **Procesamiento de flujos con Flink**
✅ **Lee desde tópico de respuestas exitosas**
✅ **Aplica función de score (BERTScore)**
✅ **Decisión basada en resultado**
✅ **Reinyección de preguntas de baja calidad**
✅ **Mecanismo anti-ciclos infinitos**
✅ **Contenerizado con Docker**

## 📝 Notas Técnicas

- El job usa **Kafka Source** con offset latest (solo procesa nuevos mensajes)
- El cálculo de BERTScore se delega a `score_validator` via HTTP
- Si el servicio de scoring no responde, usa score por defecto (0.5) para no bloquear
- El job corre en modo **detached** (-d) para continuar después del despliegue
- TaskManager configurado con 1 réplica (escalable según necesidad)
