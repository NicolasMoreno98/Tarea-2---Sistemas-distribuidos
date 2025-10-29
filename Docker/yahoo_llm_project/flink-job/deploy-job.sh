#!/bin/bash
# Script para compilar y desplegar el Flink job

echo "🔨 Compilando Flink job con Maven..."

# Compilar el proyecto
mvn clean package -DskipTests

if [ $? -ne 0 ]; then
    echo "❌ Error al compilar el proyecto"
    exit 1
fi

echo "✅ Compilación exitosa"
echo "📦 JAR generado: target/flink-score-validator-1.0.jar"

# Esperar a que Flink JobManager esté listo
echo "⏳ Esperando a que Flink JobManager esté disponible..."
sleep 10

# Desplegar el job en Flink
echo "🚀 Desplegando job en Flink..."
docker exec flink_jobmanager flink run \
    -d \
    /opt/flink-job/target/flink-score-validator-1.0.jar

if [ $? -eq 0 ]; then
    echo "✅ Job desplegado exitosamente"
    echo "🌐 Accede a Flink UI en: http://localhost:8081"
else
    echo "❌ Error al desplegar el job"
    exit 1
fi
