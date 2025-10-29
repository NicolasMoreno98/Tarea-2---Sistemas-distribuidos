#!/bin/bash

echo "=== Yahoo LLM Evaluation System ==="
echo "Este script ejecutará el sistema completo para procesar 10,000 preguntas aleatorias"
echo "de las primeras 20,000 del dataset train.csv"
echo ""

# Verificar que existe el dataset
if [ ! -f "./dataset/train.csv" ]; then
    echo "ERROR: No se encontró el archivo dataset/train.csv"
    echo "Por favor, coloca el archivo train.csv en la carpeta dataset/"
    exit 1
fi

echo "✓ Dataset encontrado"
echo ""

# Construir y levantar los servicios
echo "🐳 Construyendo y levantando servicios Docker..."
docker-compose up --build -d

echo ""
echo "⏳ Esperando a que los servicios estén listos..."
sleep 30

# Verificar que los servicios estén funcionando
echo "🔍 Verificando servicios..."
echo "- Redis: $(docker-compose ps redis | grep 'Up' > /dev/null && echo '✓ OK' || echo '✗ Error')"
echo "- PostgreSQL: $(docker-compose ps postgres | grep 'Up' > /dev/null && echo '✓ OK' || echo '✗ Error')"
echo "- LLM Service: $(docker-compose ps llm-service | grep 'Up' > /dev/null && echo '✓ OK' || echo '✗ Error')"

echo ""
echo "🚀 Ejecutando generador de tráfico..."
echo "Esto tomará varios minutos dependiendo de la velocidad de la API de Gemini..."

# Ejecutar el generador de tráfico
docker-compose run --rm traffic-generator

echo ""
echo "📊 Resultados guardados en dataset/response.json"
echo ""

# Mostrar estadísticas básicas si el archivo fue creado
if [ -f "./dataset/response.json" ]; then
    echo "=== Resumen de Ejecución ==="
    echo "Archivo de resultados creado exitosamente"
    echo "Puedes revisar las estadísticas detalladas en dataset/response.json"
else
    echo "⚠️  No se encontró el archivo de resultados"
fi

echo ""
echo "🐳 Para detener los servicios ejecuta: docker-compose down"
echo "📁 Los resultados están en: ./dataset/response.json"
