"""
Script para generar reporte final del experimento de 1000 consultas
Se ejecuta automáticamente cuando se completen las 1000 consultas
"""

import subprocess
import json
from datetime import datetime

KAFKA_CONTAINER = "kafka_broker"

TOPICS = [
    "questions-pending",
    "llm-responses-success",
    "llm-responses-error-overload",
    "llm-responses-error-quota",
    "validated-responses"
]

def get_topic_info(topic):
    """Obtiene información del tópico"""
    try:
        cmd = f'docker exec {KAFKA_CONTAINER} kafka-get-offsets --broker-list localhost:9092 --topic {topic}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
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

def get_postgres_stats():
    """Obtiene estadísticas detalladas de PostgreSQL"""
    try:
        queries = {
            'total': "SELECT COUNT(*) FROM responses;",
            'avg_score': "SELECT ROUND(AVG(bert_score)::numeric, 4) FROM responses;",
            'min_score': "SELECT ROUND(MIN(bert_score)::numeric, 4) FROM responses;",
            'max_score': "SELECT ROUND(MAX(bert_score)::numeric, 4) FROM responses;",
            'approved': "SELECT COUNT(*) FROM responses WHERE bert_score >= 0.80;",
            'rejected': "SELECT COUNT(*) FROM responses WHERE bert_score < 0.80;",
            'by_attempts': """
                SELECT processing_attempts, COUNT(*) as count, 
                       ROUND(AVG(bert_score)::numeric, 4) as avg_score
                FROM responses 
                GROUP BY processing_attempts 
                ORDER BY processing_attempts;
            """
        }
        
        stats = {}
        for key, query in queries.items():
            cmd = f'docker exec postgres_db psql -U user -d yahoo_db -t -c "{query}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                if key == 'by_attempts':
                    # Parsear múltiples líneas
                    attempts_data = []
                    for line in result.stdout.strip().split('\n'):
                        if line.strip() and '|' in line:
                            parts = [p.strip() for p in line.split('|')]
                            if len(parts) >= 3 and parts[0].isdigit():
                                attempts_data.append({
                                    'attempts': int(parts[0]),
                                    'count': int(parts[1]),
                                    'avg_score': float(parts[2])
                                })
                    stats[key] = attempts_data
                else:
                    stats[key] = result.stdout.strip()
        
        return stats
    except Exception as e:
        print(f"Error obteniendo stats de PostgreSQL: {e}")
        return {}

def generate_report():
    """Genera el reporte final completo"""
    print("\n" + "="*100)
    print("REPORTE FINAL - EXPERIMENTO 1000 CONSULTAS")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100)
    
    # Estadísticas de Kafka
    print("\n📊 ESTADÍSTICAS DE TÓPICOS KAFKA")
    print("-"*100)
    print(f"{'Tópico':<30} {'Total Mensajes':>20} {'Descripción':<45}")
    print("-"*100)
    
    topic_stats = {}
    descriptions = {
        "questions-pending": "Preguntas nuevas enviadas",
        "llm-responses-success": "Respuestas exitosas del LLM",
        "llm-responses-error-overload": "Errores de sobrecarga",
        "llm-responses-error-quota": "Errores de cuota",
        "validated-responses": "Validadas y persistidas"
    }
    
    for topic in TOPICS:
        count = get_topic_info(topic)
        topic_stats[topic] = count
        desc = descriptions.get(topic, "")
        print(f"{topic:<30} {count:>20,} {desc:<45}")
    
    print("-"*100)
    
    # Estadísticas de PostgreSQL
    print("\n💾 ESTADÍSTICAS DE BASE DE DATOS")
    print("-"*100)
    
    db_stats = get_postgres_stats()
    
    total = int(db_stats.get('total', 0))
    avg_score = float(db_stats.get('avg_score', 0))
    min_score = float(db_stats.get('min_score', 0))
    max_score = float(db_stats.get('max_score', 0))
    approved = int(db_stats.get('approved', 0))
    rejected = int(db_stats.get('rejected', 0))
    
    print(f"Total de respuestas almacenadas:    {total:>10,}")
    print(f"Respuestas aprobadas (≥0.80):       {approved:>10,} ({approved/total*100:.2f}%)")
    print(f"Respuestas rechazadas (<0.80):      {rejected:>10,} ({rejected/total*100:.2f}%)")
    print(f"\nScore promedio:                     {avg_score:>10.4f}")
    print(f"Score mínimo:                       {min_score:>10.4f}")
    print(f"Score máximo:                       {max_score:>10.4f}")
    print("-"*100)
    
    # Distribución por intentos
    print("\n📈 DISTRIBUCIÓN POR INTENTOS DE PROCESAMIENTO")
    print("-"*100)
    print(f"{'Intentos':<15} {'Cantidad':>15} {'% del Total':>15} {'Score Promedio':>20}")
    print("-"*100)
    
    attempts_data = db_stats.get('by_attempts', [])
    for item in attempts_data:
        attempts = item['attempts']
        count = item['count']
        pct = count / total * 100 if total > 0 else 0
        avg = item['avg_score']
        print(f"{attempts:<15} {count:>15,} {pct:>14.2f}% {avg:>20.4f}")
    
    print("-"*100)
    
    # Flujo del pipeline
    print("\n🔄 ANÁLISIS DEL FLUJO DE PROCESAMIENTO")
    print("-"*100)
    
    questions_sent = topic_stats.get("questions-pending", 0)
    llm_success = topic_stats.get("llm-responses-success", 0)
    llm_overload = topic_stats.get("llm-responses-error-overload", 0)
    llm_quota = topic_stats.get("llm-responses-error-quota", 0)
    validated = topic_stats.get("validated-responses", 0)
    
    llm_total = llm_success + llm_overload + llm_quota
    
    print(f"1. Preguntas nuevas enviadas a Kafka:       {questions_sent:>10,}")
    print(f"2. Respuestas exitosas del LLM:             {llm_success:>10,}")
    print(f"3. Errores de sobrecarga del LLM:           {llm_overload:>10,}")
    print(f"4. Errores de cuota del LLM:                {llm_quota:>10,}")
    print(f"5. Total procesadas por LLM:                {llm_total:>10,}")
    print(f"6. Validadas y persistidas por Flink:       {validated:>10,}")
    print(f"\n   💾 Total persistido en PostgreSQL:       {total:>10,}")
    print("-"*100)
    
    # Conclusiones
    print("\n📋 CONCLUSIONES DEL EXPERIMENTO")
    print("-"*100)
    
    cache_hits = total - questions_sent
    cache_rate = cache_hits / total * 100 if total > 0 else 0
    
    print(f"• De 1000 consultas solicitadas:")
    print(f"  - {cache_hits:,} fueron encontradas en cache/database ({cache_rate:.1f}%)")
    print(f"  - {questions_sent:,} requirieron procesamiento asíncrono ({100-cache_rate:.1f}%)")
    print(f"\n• Tasa de aprobación con umbral 0.80: {approved/total*100:.2f}%")
    print(f"• Score promedio del sistema: {avg_score:.4f}")
    print(f"• Rango de scores: [{min_score:.4f} - {max_score:.4f}]")
    
    if attempts_data:
        total_1_attempt = next((item['count'] for item in attempts_data if item['attempts'] == 1), 0)
        if total_1_attempt > 0:
            print(f"• Éxito en primer intento: {total_1_attempt:,} respuestas ({total_1_attempt/total*100:.2f}%)")
    
    print("-"*100)
    print("\n✅ REPORTE COMPLETADO")
    print("="*100)
    
    # Guardar en archivo
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'kafka_topics': topic_stats,
        'database_stats': {
            'total': total,
            'approved': approved,
            'rejected': rejected,
            'avg_score': avg_score,
            'min_score': min_score,
            'max_score': max_score,
            'by_attempts': attempts_data
        },
        'cache_rate': cache_rate,
        'questions_processed_async': questions_sent
    }
    
    with open('experiment_report.json', 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print("\n📄 Reporte guardado en: experiment_report.json")

if __name__ == "__main__":
    generate_report()
