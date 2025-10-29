#!/usr/bin/env python3
"""
Script para obtener estadísticas de Kafka de las últimas 100 consultas
"""
from kafka import KafkaConsumer, TopicPartition
from datetime import datetime
import json

bootstrap_servers = 'localhost:9092'
topics = [
    'questions-pending',
    'llm-responses-success', 
    'llm-responses-error-overload',
    'llm-responses-error-quota',
    'validated-responses'
]

print('=' * 70)
print('ESTADÍSTICAS DE KAFKA - ÚLTIMAS 100 CONSULTAS')
print('=' * 70)

total_stats = {}

for topic in topics:
    try:
        consumer = KafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            auto_offset_reset='latest',
            enable_auto_commit=False,
            consumer_timeout_ms=1000,
            value_deserializer=lambda x: json.loads(x.decode('utf-8')) if x else None
        )
        
        # Obtener particiones
        partitions = consumer.partitions_for_topic(topic)
        if not partitions:
            print(f'\n📌 {topic}:')
            print(f'   ⚠️  Sin particiones disponibles')
            consumer.close()
            continue
        
        # Usar partición 0
        tp = TopicPartition(topic, 0)
        consumer.assign([tp])
        
        # Ir al final y obtener offset
        consumer.seek_to_end(tp)
        end_offset = consumer.position(tp)
        
        # Retroceder 100 mensajes
        start_offset = max(0, end_offset - 100)
        consumer.seek(tp, start_offset)
        
        # Leer mensajes
        messages = []
        for msg in consumer:
            messages.append(msg)
            if len(messages) >= 100:
                break
        
        count = len(messages)
        total_stats[topic] = count
        
        print(f'\n📌 {topic}:')
        print(f'   • Mensajes (últimos 100): {count}')
        print(f'   • Offset range: [{start_offset} - {end_offset}]')
        
        if messages:
            first_time = datetime.fromtimestamp(messages[0].timestamp / 1000)
            last_time = datetime.fromtimestamp(messages[-1].timestamp / 1000)
            duration = (messages[-1].timestamp - messages[0].timestamp) / 1000
            print(f'   • Período: {first_time.strftime("%H:%M:%S")} - {last_time.strftime("%H:%M:%S")} ({duration:.1f}s)')
        
        consumer.close()
        
    except Exception as e:
        print(f'\n📌 {topic}:')
        print(f'   ❌ Error: {str(e)}')
        total_stats[topic] = 0

print('\n' + '=' * 70)
print('RESUMEN DEL FLUJO (últimas 100 consultas):')
print('=' * 70)

if total_stats:
    questions = total_stats.get('questions-pending', 0)
    success = total_stats.get('llm-responses-success', 0)
    error_overload = total_stats.get('llm-responses-error-overload', 0)
    error_quota = total_stats.get('llm-responses-error-quota', 0)
    validated = total_stats.get('validated-responses', 0)
    
    print(f'\n1️⃣  questions-pending: {questions}')
    print(f'2️⃣  llm-responses-success: {success}')
    print(f'3️⃣  llm-responses-error-overload: {error_overload}')
    print(f'4️⃣  llm-responses-error-quota: {error_quota}')
    print(f'5️⃣  validated-responses: {validated}')
    
    total_responses = success + error_overload + error_quota
    if questions > 0:
        print(f'\n📊 Análisis:')
        print(f'   • Tasa de éxito LLM: {(success/questions)*100:.2f}%' if questions > 0 else '   • Tasa de éxito LLM: N/A')
        print(f'   • Errores overload: {error_overload}')
        print(f'   • Errores quota: {error_quota}')
        print(f'   • Validadas: {validated}/{success} ({(validated/success)*100:.2f}%)' if success > 0 else '   • Validadas: 0/0')

print('\n' + '=' * 70)
