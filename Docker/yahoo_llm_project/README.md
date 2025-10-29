# Yahoo LLM Evaluation System - Tarea 1 Sistemas Distribuidos

## Descripcin del Proyecto

Sistema distribuido de evaluacin de LLM (Large Language Model) que utiliza el dataset de Yahoo Answers para procesar preguntas y generar respuestas usando Ollama como LLM local. El sistema implementa cache con Redis y persistencia con PostgreSQL.

## Arquitectura del Sistema

```
        
  Traffic               LLM Service            Ollama      
  Generator         (Flask API)      (Local LLM)   
        
                                
                                
                       
                             Redis      
                            (Cache)     
                       
                                
                                
                       
                          PostgreSQL    
                          (Database)    
                       
```

## Requisitos Previos

### 1. Instalar Docker Desktop
- Descargar desde: https://www.docker.com/products/docker-desktop/
- Verificar instalacin: `docker --version`

### 2. Instalar Ollama
- Windows: Descargar desde https://ollama.ai/
- Linux/macOS: `curl -fsSL https://ollama.ai/install.sh | sh`
- Verificar instalacin: `ollama --version`

### 3. Descargar Modelo TinyLlama (Recomendado)
```bash
ollama pull tinyllama:latest
```
Nota: TinyLlama es ultra-rpido (637MB) - ideal para demostraciones

## Gua de Ejecucin Paso a Paso

### Paso 1: Preparar el Entorno

IMPORTANTE: Ejecutar todos los comandos desde la carpeta raz del proyecto donde est ubicado el archivo docker-compose.yml

En Windows:
```cmd
# Navegar al directorio del proyecto (ejemplo)
cd "D:\U\Sistemas Distribuidos\Docker\yahoo_llm_project"

# Verificar que ests en la ubicacin correcta
dir docker-compose.yml

# Verificar que Ollama est corriendo
ollama list
```

### Paso 2: Configurar Nmero de Consultas (OPCIONAL)
Si deseas cambiar el nmero de consultas a procesar:

```bash
# Abrir el archivo de configuracin
notepad traffic_generator/generator.py

# Modificar la lnea 14:
NUM_REQUESTS = 10  # Cambiar este nmero (1-10000)
```

Opciones recomendadas:
- Demo rpida: NUM_REQUESTS = 10 (aprox. 20 segundos)
- Prueba mediana: NUM_REQUESTS = 100 (aprox. 3 minutos)
- Experimento completo: NUM_REQUESTS = 10000 (aprox. 3 horas)

### Paso 3: Levantar el Sistema
```bash
# Construir y levantar todos los servicios
docker-compose up -d

# Verificar que todos los servicios estn corriendo
docker ps
```

Deberas ver 4 contenedores activos:
- `yahoo_llm_project-postgres-1`
- `yahoo_llm_project-redis-1`  
- `yahoo_llm_project-llm-service-1`
- `yahoo_llm_project-traffic-generator-1`

### Paso 4: Verificar Conectividad del Sistema
```bash
# Probar la salud del servicio LLM
curl http://localhost:5000/health

# O en PowerShell:
Invoke-WebRequest -Uri http://localhost:5000/health -Method GET
```

### Paso 5: Ejecutar el Experimento
```bash
# Ejecutar el generador de trfico
docker exec -it yahoo_llm_project-traffic-generator-1 python /app/generator.py
```

### Paso 6: Monitorear Progreso (OPCIONAL)
En terminales separadas puedes monitorear:

```bash
# Ver logs del servicio LLM
docker logs -f yahoo_llm_project-llm-service-1

# Ver logs del generador
docker logs -f yahoo_llm_project-traffic-generator-1

# Ver estado de la base de datos
docker exec -it yahoo_llm_project-postgres-1 psql -U user -d yahoo_db -c "SELECT COUNT(*) FROM responses;"
```

## Flujo de Guardado de Datos

El sistema guarda los resultados en DOS ubicaciones simultneamente:

### 1. Base de Datos PostgreSQL (Principal)
Cada respuesta se guarda inmediatamente en la tabla `responses` con:
- ID nico de pregunta
- Texto de la pregunta
- Respuesta humana (del dataset)
- Respuesta del LLM
- Score BERTScore
- Timestamp de creacin

### 2. Archivo JSON (Respaldo y Resumen)
Al finalizar el experimento se genera `dataset/response.json` con:
- Resumen estadstico del experimento
- Array completo de todas las respuestas procesadas
- Metadatos del experimento (timestamps, configuracin, etc.)

## Interpretacin de Resultados

Durante la ejecucin se mostrar:

```
INICIANDO EXPERIMENTO OLLAMA - 10 REQUESTS
Request 1/10 - ID: 12345
Pregunta: What is the meaning of life?
  Ollama respondi (2.1s) - Score: 0.852
  Respuesta: The meaning of life is...

ESTADSTICAS FINALES:
  Total requests: 10
  Requests exitosas: 10 (100.0%)
  Cache hits: 2 (20.0%)
  LLM calls: 8 (80.0%)
```

Mtricas importantes:
- Cache hits: Preguntas ya procesadas (respuesta instantnea)
- LLM calls: Preguntas nuevas (procesadas por Ollama)
- Score: Similaridad BERTScore (0-1, donde 1 = idntico)

## Ubicacin de Datos Guardados

### 1. Base de Datos PostgreSQL
```bash
# Ver todas las respuestas
docker exec -it yahoo_llm_project-postgres-1 psql -U user -d yahoo_db -c "SELECT * FROM responses LIMIT 5;"

# Contar total de respuestas
docker exec -it yahoo_llm_project-postgres-1 psql -U user -d yahoo_db -c "SELECT COUNT(*) FROM responses;"

# Exportar respaldo completo
docker exec yahoo_llm_project-postgres-1 pg_dump -U user yahoo_db > backup_$(date +%Y%m%d).sql
```

### 2. Archivo JSON de Resultados
```
Ubicacin: dataset/response.json
```

```bash
# Ver resumen del ltimo experimento (Windows)
Get-Content dataset/response.json | ConvertFrom-Json | Select-Object -ExpandProperty summary

# Ver resumen (Linux/macOS)
cat dataset/response.json | jq '.summary'
```

### 3. Cache Redis
```bash
# Ver claves en cache
docker exec -it yahoo_llm_project-redis-1 redis-cli KEYS "*"

# Ver estadsticas de cache
docker exec -it yahoo_llm_project-redis-1 redis-cli INFO memory
```

## Apagar el Sistema

### Opcin 1: Suspender (Mantener Datos)
```bash
# Detener contenedores pero mantener volmenes de datos
docker-compose stop
```

### Opcin 2: Apagar Completamente
```bash
# Eliminar contenedores pero mantener volmenes
docker-compose down
```

### Opcin 3: Limpieza Total (ADVERTENCIA: ELIMINA TODOS LOS DATOS)
```bash
# CUIDADO: Esto eliminar TODOS los datos
docker-compose down -v
docker system prune -f
```

## Solucin de Problemas

### Error: "model not found"
```bash
# Verificar modelos disponibles
ollama list

# Si no hay modelos, descargar TinyLlama
ollama pull tinyllama:latest
```

### Error: Puerto ocupado
```bash
# Verificar puertos en uso
netstat -an | findstr "5000\|5432\|6379"

# Cambiar puertos en docker-compose.yml si es necesario
```

### Performance lento
```bash
# Usar TinyLlama para mxima velocidad
ollama pull tinyllama:latest

# Reducir NUM_REQUESTS para pruebas rpidas
NUM_REQUESTS = 10
```

## Configuraciones de Rendimiento

### Para Demostraciones Rpidas (menos de 1 minuto)
- Modelo: tinyllama:latest
- Requests: NUM_REQUESTS = 5
- Tiempo esperado: aproximadamente 15 segundos

### Para Evaluacin Acadmica (menos de 5 minutos)
- Modelo: tinyllama:latest
- Requests: NUM_REQUESTS = 50
- Tiempo esperado: aproximadamente 2 minutos

### Para Experimento Completo (menos de 3 horas)
- Modelo: tinyllama:latest
- Requests: NUM_REQUESTS = 10000
- Tiempo esperado: aproximadamente 2-3 horas

## Informacin Acadmica

Curso: Sistemas Distribuidos 2025-2
Tarea: Tarea 1 - Sistema de Evaluacin LLM
Tecnologas: Docker, PostgreSQL, Redis, Flask, Ollama, BERTScore
Dataset: Yahoo Answers (745MB, 20,000 preguntas)

### Cumplimiento de Requisitos
- Containerizacin: Docker Compose con 4 servicios
- Cache distribuido: Redis con poltica LRU y TTL de 1 hora
- Base de datos: PostgreSQL con persistencia
- LLM Local: Ollama con TinyLlama
- Evaluacin: BERTScore para similaridad semntica
- Escalabilidad: Arquitectura de microservicios

### Configuracin de Cache Redis
- Poltica de eviccin: LRU (Least Recently Used)
- Memoria mxima: 2MB (aprox. 1000 consultas)  
- TTL por clave: 3600 segundos (1 hora)
- Persistencia: Habilitada con snapshots automticos

## Soporte

Para dudas tcnicas o problemas de ejecucin, revisar logs:
```bash
docker-compose logs --tail=50
```
