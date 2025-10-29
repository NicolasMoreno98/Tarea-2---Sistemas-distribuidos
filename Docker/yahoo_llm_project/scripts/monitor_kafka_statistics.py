"""
Script para monitorear estadísticas de tópicos Kafka durante experimento de 1000 consultas
Tarea 2 - Sistemas Distribuidos
"""

import subprocess
import json
import time
from datetime import datetime
import sys

KAFKA_CONTAINER = "kafka_broker"

TOPICS = [
    "questions-pending",
    "llm-responses-success",
    "llm-responses-error-overload",
    "llm-responses-error-quota",
    "validated-responses"
]

def get_topic_info(topic):
    """Obtiene información del tópico usando kafka-get-offsets"""
    try:
        cmd = f'docker exec {KAFKA_CONTAINER} kafka-get-offsets --broker-list localhost:9092 --topic {topic}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            # Parsear salida: topic:partition:offset
            total_messages = 0
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(':')
                    if len(parts) == 3:
                        offset = int(parts[2])
                        total_messages += offset
            return total_messages
        return 0
    except Exception as e:
        print(f"Error obteniendo info de {topic}: {e}")
        return 0

def get_consumer_lag(group_id):
    """Obtiene el lag de un consumer group"""
    try:
        cmd = f'docker exec {KAFKA_CONTAINER} kafka-consumer-groups.sh --bootstrap-server localhost:9092 --group {group_id} --describe'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            total_lag = 0
            for line in result.stdout.strip().split('\n'):
                if 'LAG' not in line and line.strip():
                    parts = line.split()
                    if len(parts) >= 6:
                        try:
                            lag = int(parts[5])
                            total_lag += lag
                        except:
                            pass
            return total_lag
        return 0
    except Exception as e:
        return 0

def get_postgres_stats():
    """Obtiene estadísticas de PostgreSQL"""
    try:
        cmd = 'docker exec postgres_db psql -U user -d yahoo_db -t -c "SELECT COUNT(*) FROM responses;"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            total = int(result.stdout.strip())
            return total
        return 0
    except Exception as e:
        return 0

def print_statistics():
    """Imprime estadísticas completas del sistema"""
    print("\n" + "="*100)
    print(f"ESTADÍSTICAS KAFKA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100)
    
    # Estadísticas por tópico
    print("\n📊 MENSAJES POR TÓPICO:")
    print("-" * 100)
    print(f"{'Tópico':<30} {'Total Mensajes':>15} {'Descripción':<50}")
    print("-" * 100)
    
    topic_stats = {}
    descriptions = {
        "questions-pending": "Preguntas nuevas enviadas a procesar",
        "llm-responses-success": "Respuestas exitosas del LLM",
        "llm-responses-error-overload": "Errores de sobrecarga del LLM",
        "llm-responses-error-quota": "Errores de cuota excedida del LLM",
        "validated-responses": "Respuestas validadas y persistidas"
    }
    
    for topic in TOPICS:
        count = get_topic_info(topic)
        topic_stats[topic] = count
        desc = descriptions.get(topic, "")
        print(f"{topic:<30} {count:>15,} {desc:<50}")
    
    print("-" * 100)
    
    # Estadísticas de consumers
    print("\n⚙️  LAG DE CONSUMERS:")
    print("-" * 100)
    print(f"{'Consumer Group':<40} {'Lag':>15}")
    print("-" * 100)
    
    consumer_groups = [
        "llm-consumer-group",
        "score-validator-group",
        "retry-overload-group",
        "retry-quota-group"
    ]
    
    total_lag = 0
    for group in consumer_groups:
        lag = get_consumer_lag(group)
        total_lag += lag
        print(f"{group:<40} {lag:>15,}")
    
    print("-" * 100)
    print(f"{'TOTAL LAG':<40} {total_lag:>15,}")
    print("-" * 100)
    
    # Estadísticas de PostgreSQL
    print("\n💾 BASE DE DATOS:")
    print("-" * 100)
    postgres_count = get_postgres_stats()
    print(f"Total respuestas en PostgreSQL: {postgres_count:,}")
    print("-" * 100)
    
    # Flujo del pipeline
    print("\n🔄 ANÁLISIS DEL FLUJO:")
    print("-" * 100)
    
    questions_sent = topic_stats.get("questions-pending", 0)
    llm_success = topic_stats.get("llm-responses-success", 0)
    llm_overload = topic_stats.get("llm-responses-error-overload", 0)
    llm_quota = topic_stats.get("llm-responses-error-quota", 0)
    validated = topic_stats.get("validated-responses", 0)
    
    llm_total = llm_success + llm_overload + llm_quota
    
    print(f"1. Preguntas nuevas enviadas:                {questions_sent:>10,}")
    print(f"2. Respuestas exitosas del LLM:              {llm_success:>10,}")
    print(f"3. Errores de sobrecarga del LLM:            {llm_overload:>10,}")
    print(f"4. Errores de cuota del LLM:                 {llm_quota:>10,}")
    print(f"5. Total procesadas por LLM:                 {llm_total:>10,}")
    print(f"6. Validadas y persistidas (Flink):          {validated:>10,}")
    print(f"\n   💾 Total en PostgreSQL:                   {postgres_count:>10,}")
    print(f"   ⏳ Pendientes de procesar (lag):          {total_lag:>10,}")
    print("-" * 100)
    
    # Tasas de conversión
    if questions_sent > 0:
        print("\n📈 TASAS DE ÉXITO:")
        print("-" * 100)
        print(f"Tasa de respuesta LLM:          {llm_total/questions_sent*100:>6.2f}%")
        if llm_total > 0:
            print(f"Tasa de éxito LLM:              {llm_success/llm_total*100:>6.2f}%")
            print(f"Tasa de validación Flink:       {validated/llm_success*100:>6.2f}%")
        print("-" * 100)
    
    return {
        'topics': topic_stats,
        'lag': total_lag,
        'postgres': postgres_count,
        'timestamp': datetime.now().isoformat()
    }

def monitor_continuous(interval=10, duration=None):
    """Monitoreo continuo con intervalo especificado"""
    print("🚀 INICIANDO MONITOREO DE KAFKA")
    print(f"Intervalo: {interval} segundos")
    if duration:
        print(f"Duración: {duration} segundos")
    else:
        print("Duración: Indefinida (Ctrl+C para detener)")
    
    start_time = time.time()
    iteration = 0
    
    try:
        while True:
            iteration += 1
            stats = print_statistics()
            
            # Verificar si terminó el procesamiento
            if stats['lag'] == 0 and stats['postgres'] >= 1000:
                print("\n✅ PROCESAMIENTO COMPLETADO!")
                print(f"Total de iteraciones: {iteration}")
                print(f"Tiempo total: {time.time() - start_time:.2f} segundos")
                break
            
            # Verificar duración
            if duration and (time.time() - start_time) >= duration:
                print(f"\n⏱️  Tiempo de monitoreo completado ({duration}s)")
                break
            
            print(f"\n⏳ Esperando {interval} segundos... (Iteración {iteration})")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Monitoreo detenido por el usuario")
        print(f"Total de iteraciones: {iteration}")
        print(f"Tiempo total: {time.time() - start_time:.2f} segundos")

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "once":
            print_statistics()
        elif sys.argv[1] == "monitor":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            duration = int(sys.argv[3]) if len(sys.argv) > 3 else None
            monitor_continuous(interval, duration)
        else:
            print("Uso: python monitor_kafka_statistics.py [once|monitor [interval] [duration]]")
    else:
        # Por defecto: monitoreo continuo cada 10 segundos
        monitor_continuous(10)

if __name__ == "__main__":
    main()
