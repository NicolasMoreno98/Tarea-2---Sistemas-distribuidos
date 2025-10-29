"""
Script para reenviar respuestas existentes a Flink para procesamiento
Tarea 2 - Sistemas Distribuidos

Este script lee las respuestas de PostgreSQL y las reenvía al tópico
'llm-responses-success' para que Flink las procese y calcule los scores.
"""

import psycopg2
import json
import time
import logging
import sys
from kafka import KafkaProducer
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración
DATABASE_URL = "postgresql://user:password@localhost:5432/yahoo_db"
KAFKA_BROKER = "localhost:9093"
KAFKA_TOPIC = "llm-responses-success"

def create_kafka_producer():
    """Crea un productor de Kafka"""
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BROKER],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='all',
            retries=3
        )
        logger.info(f"✅ Conectado a Kafka: {KAFKA_BROKER}")
        return producer
    except Exception as e:
        logger.error(f"❌ Error conectando a Kafka: {e}")
        sys.exit(1)

def reset_bert_scores():
    """Resetea los bert_scores a NULL para que Flink los recalcule"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        logger.info("🔄 Reseteando bert_scores a NULL...")
        cursor.execute("UPDATE responses SET bert_score = NULL")
        affected = cursor.rowcount
        conn.commit()
        
        logger.info(f"✅ {affected} scores reseteados")
        
        cursor.close()
        conn.close()
        return affected
    except Exception as e:
        logger.error(f"❌ Error reseteando scores: {e}")
        sys.exit(1)

def reprocess_responses():
    """Lee respuestas de PostgreSQL y las envía a Kafka"""
    try:
        # Conectar a PostgreSQL
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Contar total
        cursor.execute("SELECT COUNT(*) FROM responses")
        total = cursor.fetchone()[0]
        
        logger.info(f"📊 Total de respuestas a reprocesar: {total}")
        
        # Obtener todas las respuestas
        cursor.execute("""
            SELECT 
                question_id,
                question_text,
                llm_response,
                original_answer,
                processing_attempts,
                created_at
            FROM responses
            ORDER BY created_at
        """)
        
        responses = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Crear productor de Kafka
        producer = create_kafka_producer()
        
        logger.info("🚀 Iniciando reenvío a Kafka...")
        start_time = time.time()
        sent = 0
        errors = 0
        
        for question_id, question_text, llm_response, original_answer, attempts, created_at in responses:
            try:
                # Crear mensaje para Flink
                message = {
                    'question_id': question_id,
                    'question': question_text,
                    'llm_response': llm_response,
                    'original_answer': original_answer,
                    'processing_attempts': attempts or 1,
                    'timestamp': created_at.isoformat() if created_at else datetime.now().isoformat(),
                    'reprocessed': True  # Flag para identificar que es reprocesado
                }
                
                # Enviar a Kafka
                future = producer.send(KAFKA_TOPIC, value=message)
                future.get(timeout=10)  # Esperar confirmación
                
                sent += 1
                
                # Log de progreso cada 500 respuestas
                if sent % 500 == 0:
                    elapsed = time.time() - start_time
                    rate = sent / elapsed if elapsed > 0 else 0
                    remaining = (total - sent) / rate if rate > 0 else 0
                    
                    logger.info(
                        f"✓ Enviadas: {sent}/{total} ({sent/total*100:.1f}%) | "
                        f"Rate: {rate:.1f} msg/s | "
                        f"ETA: {remaining:.0f}s"
                    )
                
                # Pequeña pausa para no saturar
                if sent % 100 == 0:
                    time.sleep(0.1)
                
            except Exception as e:
                errors += 1
                logger.error(f"❌ Error enviando {question_id}: {e}")
                continue
        
        # Flush final
        producer.flush()
        producer.close()
        
        # Estadísticas finales
        elapsed_time = time.time() - start_time
        logger.info("=" * 70)
        logger.info("✅ REENVÍO COMPLETADO")
        logger.info(f"📊 Estadísticas:")
        logger.info(f"   • Total enviadas: {sent}")
        logger.info(f"   • Errores: {errors}")
        logger.info(f"   • Tiempo total: {elapsed_time:.2f} segundos")
        logger.info(f"   • Velocidad promedio: {sent/elapsed_time:.2f} mensajes/segundo")
        logger.info("=" * 70)
        logger.info("")
        logger.info("⏳ IMPORTANTE:")
        logger.info("   Flink ahora procesará estas respuestas y calculará los scores.")
        logger.info("   Puedes monitorear el progreso en:")
        logger.info("   • Flink UI: http://localhost:8081")
        logger.info("   • Kafka UI: http://localhost:8080")
        logger.info("   • Dashboard: http://localhost:5002")
        logger.info("")
        logger.info(f"   Tiempo estimado de procesamiento: ~{total * 2 / 60:.1f} minutos")
        
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("🔄 SCRIPT DE REPROCESAMIENTO CON FLINK")
    logger.info("=" * 70)
    logger.info("Este script reenviará todas las respuestas existentes a Flink")
    logger.info("para que calcule los scores según su lógica de procesamiento.")
    logger.info("")
    logger.info("Pasos:")
    logger.info("1. Resetear bert_scores a NULL en PostgreSQL")
    logger.info("2. Reenviar respuestas al tópico 'llm-responses-success'")
    logger.info("3. Flink procesará y calculará scores automáticamente")
    logger.info("=" * 70)
    
    input("\n⚠️  Presiona ENTER para continuar o CTRL+C para cancelar...")
    
    try:
        # Paso 1: Resetear scores
        reset_bert_scores()
        
        # Paso 2: Reenviar a Kafka
        reprocess_responses()
        
        logger.info("\n✅ Script finalizado exitosamente")
        logger.info("   Espera unos minutos y verifica el dashboard en http://localhost:5002")
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ Error fatal: {e}")
        sys.exit(1)
