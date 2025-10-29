#!/usr/bin/env python3
"""
Script para monitorear experimento y generar reporte completo al finalizar
"""
import subprocess
import time
import json
import re
from datetime import datetime

def run_command(cmd):
    """Ejecutar comando y retornar output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {str(e)}"

def check_traffic_generator_status():
    """Verificar si el traffic generator está corriendo"""
    output = run_command('docker ps --filter "name=traffic_generator" --format "{{.Status}}"')
    return "Up" in output

def get_traffic_generator_logs():
    """Obtener logs del traffic generator"""
    return run_command('docker logs traffic_generator 2>&1')

def parse_traffic_stats(logs):
    """Extraer estadísticas de los logs del traffic generator"""
    stats = {}
    
    # Buscar estadísticas finales
    if "ESTADÍSTICAS FINALES" in logs or "ESTADISTICAS FINALES" in logs:
        # Total requests
        match = re.search(r'Total requests:\s*(\d+)', logs)
        if match:
            stats['total_requests'] = int(match.group(1))
        
        # Requests exitosas
        match = re.search(r'Requests exitosas:\s*(\d+)', logs)
        if match:
            stats['successful_requests'] = int(match.group(1))
        
        # Cache hits
        match = re.search(r'Cache hits:\s*(\d+)', logs)
        if match:
            stats['cache_hits'] = int(match.group(1))
        
        # LLM calls
        match = re.search(r'LLM calls:\s*(\d+)', logs)
        if match:
            stats['llm_calls'] = int(match.group(1))
        
        # Scores
        match = re.search(r'Score promedio:\s*([\d.]+)', logs)
        if match:
            stats['avg_score'] = float(match.group(1))
        
        match = re.search(r'Score máximo:\s*([\d.]+)', logs)
        if match:
            stats['max_score'] = float(match.group(1))
        
        match = re.search(r'Score mínimo:\s*([\d.]+)', logs)
        if match:
            stats['min_score'] = float(match.group(1))
    
    return stats

def get_kafka_offsets():
    """Obtener offsets actuales de todos los tópicos"""
    topics = ['questions-pending', 'llm-responses-success', 'llm-responses-error-overload', 
              'llm-responses-error-quota', 'validated-responses']
    
    offsets = {}
    for topic in topics:
        output = run_command(f'docker exec kafka_broker kafka-run-class kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic {topic} --time -1 2>&1')
        match = re.search(r':0:(\d+)', output)
        if match:
            offsets[topic] = int(match.group(1))
        else:
            offsets[topic] = 0
    
    return offsets

def get_database_stats():
    """Obtener estadísticas de la base de datos"""
    query = '''SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE bert_score >= 0.80) as aprobadas,
        COUNT(*) FILTER (WHERE bert_score < 0.80) as rechazadas,
        ROUND(AVG(bert_score)::numeric, 4) as score_promedio,
        ROUND(MIN(bert_score)::numeric, 4) as score_min,
        ROUND(MAX(bert_score)::numeric, 4) as score_max
    FROM responses;'''
    
    output = run_command(f'docker exec postgres_db psql -U user -d yahoo_db -t -c "{query}"')
    
    stats = {}
    if output and '|' in output:
        parts = [p.strip() for p in output.split('|')]
        if len(parts) >= 6:
            stats['total'] = int(parts[0])
            stats['approved'] = int(parts[1])
            stats['rejected'] = int(parts[2])
            stats['avg_score'] = float(parts[3])
            stats['min_score'] = float(parts[4])
            stats['max_score'] = float(parts[5])
    
    return stats

def print_report(initial_offsets, final_offsets, traffic_stats, db_stats):
    """Imprimir reporte completo"""
    print("\n" + "="*80)
    print("REPORTE COMPLETO DEL EXPERIMENTO")
    print("="*80)
    print(f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Estadísticas del Traffic Generator
    print("\nESTADISTICAS DEL EXPERIMENTO:")
    print("-"*80)
    if traffic_stats:
        total = traffic_stats.get('total_requests', 0)
        successful = traffic_stats.get('successful_requests', 0)
        cache_hits = traffic_stats.get('cache_hits', 0)
        llm_calls = traffic_stats.get('llm_calls', 0)
        
        print(f"  * Total requests: {total}")
        print(f"  * Requests exitosas: {successful} ({(successful/total*100):.1f}%)" if total > 0 else "  * Requests exitosas: 0")
        print(f"  * Cache hits: {cache_hits} ({(cache_hits/total*100):.1f}%)" if total > 0 else "  * Cache hits: 0")
        print(f"  * LLM calls: {llm_calls} ({(llm_calls/total*100):.1f}%)" if total > 0 else "  * LLM calls: 0")
        
        if 'avg_score' in traffic_stats:
            print(f"\n  Scores (BERTScore):")
            print(f"     - Promedio: {traffic_stats['avg_score']:.4f}")
            print(f"     - Maximo: {traffic_stats['max_score']:.4f}")
            print(f"     - Minimo: {traffic_stats['min_score']:.4f}")
    else:
        print("  [AVISO] No se encontraron estadisticas del traffic generator")
    
    # Flujo de Kafka
    print("\n" + "="*80)
    print("FLUJO DE MENSAJES EN KAFKA (Durante el experimento):")
    print("="*80)
    
    new_messages = {}
    for topic in initial_offsets.keys():
        delta = final_offsets.get(topic, 0) - initial_offsets.get(topic, 0)
        new_messages[topic] = delta
        
        print(f"\n{topic}:")
        print(f"  * Offset inicial: {initial_offsets.get(topic, 0)}")
        print(f"  * Offset final: {final_offsets.get(topic, 0)}")
        print(f"  * Nuevos mensajes: {delta}")
    
    # Análisis del flujo
    print("\n" + "="*80)
    print("ANALISIS DEL FLUJO:")
    print("="*80)
    
    questions = new_messages.get('questions-pending', 0)
    success = new_messages.get('llm-responses-success', 0)
    error_overload = new_messages.get('llm-responses-error-overload', 0)
    error_quota = new_messages.get('llm-responses-error-quota', 0)
    validated = new_messages.get('validated-responses', 0)
    
    print(f"\n  [1] questions-pending: {questions} mensajes")
    print(f"  [2] llm-responses-success: {success} mensajes")
    print(f"  [3] llm-responses-error-overload: {error_overload} mensajes")
    print(f"  [4] llm-responses-error-quota: {error_quota} mensajes")
    print(f"  [5] validated-responses: {validated} mensajes")
    
    total_responses = success + error_overload + error_quota
    if questions > 0:
        print(f"\n  Metricas:")
        print(f"     * Tasa de exito LLM: {(success/questions*100):.2f}%")
        print(f"     * Tasa de errores: {((error_overload+error_quota)/questions*100):.2f}%")
        if success > 0:
            print(f"     * Tasa de validacion: {(validated/success*100):.2f}%")
    
    # Estadísticas de la Base de Datos
    print("\n" + "="*80)
    print("ESTADISTICAS DE LA BASE DE DATOS (Total):")
    print("="*80)
    
    if db_stats:
        total = db_stats.get('total', 0)
        approved = db_stats.get('approved', 0)
        rejected = db_stats.get('rejected', 0)
        
        print(f"\n  * Total de respuestas: {total}")
        print(f"  * Aprobadas (score >= 0.80): {approved} ({(approved/total*100):.2f}%)" if total > 0 else "  * Aprobadas: 0")
        print(f"  * Rechazadas (score < 0.80): {rejected} ({(rejected/total*100):.2f}%)" if total > 0 else "  * Rechazadas: 0")
        
        print(f"\n  Scores en DB:")
        print(f"     - Promedio: {db_stats.get('avg_score', 0):.4f}")
        print(f"     - Maximo: {db_stats.get('max_score', 0):.4f}")
        print(f"     - Minimo: {db_stats.get('min_score', 0):.4f}")
    
    # Verificación de Coherencia
    print("\n" + "="*80)
    print("VERIFICACION DE COHERENCIA:")
    print("="*80)
    
    if traffic_stats and new_messages:
        cache_hits = traffic_stats.get('cache_hits', 0)
        llm_calls = traffic_stats.get('llm_calls', 0)
        kafka_questions = new_messages.get('questions-pending', 0)
        
        print(f"\n  * Cache hits reportados: {cache_hits}")
        print(f"  * LLM calls reportados: {llm_calls}")
        print(f"  * Mensajes en Kafka (questions-pending): {kafka_questions}")
        
        if llm_calls == kafka_questions:
            print(f"  [OK] COHERENTE: LLM calls ({llm_calls}) = Kafka messages ({kafka_questions})")
        else:
            print(f"  [AVISO] DISCREPANCIA: LLM calls ({llm_calls}) != Kafka messages ({kafka_questions})")
        
        total_req = traffic_stats.get('total_requests', 0)
        if total_req == (cache_hits + llm_calls):
            print(f"  [OK] COHERENTE: Total requests ({total_req}) = Cache hits ({cache_hits}) + LLM calls ({llm_calls})")
        else:
            print(f"  [AVISO] DISCREPANCIA en conteo total")
    
    print("\n" + "="*80)
    print("FIN DEL REPORTE")
    print("="*80 + "\n")

def main():
    print("="*80)
    print("MONITOR DE EXPERIMENTO - Iniciando...")
    print("="*80)
    
    # Obtener offsets iniciales
    print("\nCapturando estado inicial de Kafka...")
    initial_offsets = get_kafka_offsets()
    print("[OK] Estado inicial capturado")
    
    for topic, offset in initial_offsets.items():
        print(f"   {topic}: {offset}")
    
    # Monitorear traffic generator
    print("\nEsperando a que el traffic generator termine...")
    print("   (Verificando cada 5 segundos...)\n")
    
    last_log_line = ""
    iteration = 0
    
    while True:
        time.sleep(5)
        iteration += 1
        
        # Obtener logs actuales
        logs = get_traffic_generator_logs()
        
        # Mostrar progreso
        if "Enviando request" in logs:
            matches = re.findall(r'Enviando request (\d+)/(\d+)', logs)
            if matches:
                current, total = matches[-1]
                print(f"   [{iteration*5}s] Progreso: {current}/{total} requests enviadas ({int(current)/int(total)*100:.1f}%)")
        
        # Verificar si terminó
        if "EXPERIMENTO OLLAMA COMPLETADO" in logs or "ESTADÍSTICAS FINALES" in logs or "ESTADISTICAS FINALES" in logs:
            print("\n[OK] Experimento completado! Generando reporte...\n")
            time.sleep(2)  # Esperar un poco más para asegurar que todo se procesó
            break
        
        # Verificar si el contenedor se detuvo
        if not check_traffic_generator_status():
            print("\n[AVISO] Traffic generator se detuvo. Generando reporte...\n")
            break
        
        # Timeout después de 20 minutos
        if iteration > 240:  # 240 * 5s = 20 minutos
            print("\n[TIMEOUT] Timeout alcanzado. Generando reporte con datos actuales...\n")
            break
    
    # Obtener estadísticas finales
    print("Recopilando estadisticas finales...")
    
    # Esperar a que Kafka procese todo
    time.sleep(3)
    
    final_offsets = get_kafka_offsets()
    logs = get_traffic_generator_logs()
    traffic_stats = parse_traffic_stats(logs)
    db_stats = get_database_stats()
    
    # Generar reporte
    print_report(initial_offsets, final_offsets, traffic_stats, db_stats)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[AVISO] Monitoreo interrumpido por el usuario\n")
    except Exception as e:
        print(f"\n[ERROR] {str(e)}\n")
