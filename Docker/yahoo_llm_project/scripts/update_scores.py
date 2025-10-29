"""
Script para calcular y asignar BERTScore a respuestas existentes
Tarea 2 - Sistemas Distribuidos

Este script procesa las respuestas ya almacenadas en PostgreSQL que no tienen
un score asignado, calcula su BERTScore y actualiza la base de datos.
"""

import psycopg2
import time
from bert_score import score as bert_score_fn
import logging
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración de base de datos (usar variable de entorno o default)
DATABASE_URL = os.environ.get(
    'DATABASE_URL', 
    "postgresql://user:password@localhost:5432/yahoo_db"
)

def calculate_bert_score(answer, reference):
    """
    Calcula BERTScore entre respuesta y referencia
    """
    try:
        # Calcular BERTScore
        P, R, F1 = bert_score_fn([answer], [reference], lang='en', verbose=False)
        
        # Retornar F1 score (promedio de precisión y recall)
        return float(F1[0])
    except Exception as e:
        logger.error(f"Error calculando BERTScore: {e}")
        return None

def update_scores_batch():
    """
    Procesa y actualiza scores en lotes para mayor eficiencia
    """
    try:
        # Conectar a PostgreSQL
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Contar respuestas sin score
        cursor.execute("""
            SELECT COUNT(*) 
            FROM responses 
            WHERE bert_score IS NULL
        """)
        total_without_score = cursor.fetchone()[0]
        
        logger.info(f"📊 Respuestas sin score: {total_without_score}")
        
        if total_without_score == 0:
            logger.info("✅ Todas las respuestas ya tienen score asignado")
            return
        
        # Obtener todas las respuestas sin score
        cursor.execute("""
            SELECT question_id, llm_response, original_answer
            FROM responses
            WHERE bert_score IS NULL
            ORDER BY created_at
        """)
        
        responses = cursor.fetchall()
        total = len(responses)
        
        logger.info(f"🚀 Iniciando cálculo de scores para {total} respuestas...")
        logger.info(f"⏱️  Tiempo estimado: ~{total * 2} segundos ({total * 2 / 60:.1f} minutos)")
        
        processed = 0
        updated = 0
        errors = 0
        start_time = time.time()
        
        for question_id, llm_response, original_answer in responses:
            try:
                # Calcular score
                bert_score_value = calculate_bert_score(llm_response, original_answer)
                
                if bert_score_value is not None:
                    # Actualizar en la base de datos
                    cursor.execute("""
                        UPDATE responses
                        SET bert_score = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE question_id = %s
                    """, (bert_score_value, question_id))
                    
                    updated += 1
                    
                    # Log de progreso cada 100 respuestas
                    if updated % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = updated / elapsed if elapsed > 0 else 0
                        remaining = (total - updated) / rate if rate > 0 else 0
                        
                        logger.info(
                            f"✓ Procesadas: {updated}/{total} ({updated/total*100:.1f}%) | "
                            f"Rate: {rate:.1f} resp/s | "
                            f"ETA: {remaining/60:.1f} min | "
                            f"Score: {bert_score_value:.3f}"
                        )
                    
                    # Commit cada 50 respuestas para no perder progreso
                    if updated % 50 == 0:
                        conn.commit()
                else:
                    errors += 1
                    logger.warning(f"⚠️  Error calculando score para {question_id}")
                
                processed += 1
                
            except Exception as e:
                errors += 1
                logger.error(f"❌ Error procesando {question_id}: {e}")
                continue
        
        # Commit final
        conn.commit()
        
        # Estadísticas finales
        elapsed_time = time.time() - start_time
        logger.info("=" * 70)
        logger.info("✅ PROCESO COMPLETADO")
        logger.info(f"📊 Estadísticas:")
        logger.info(f"   • Total procesadas: {processed}")
        logger.info(f"   • Actualizadas exitosamente: {updated}")
        logger.info(f"   • Errores: {errors}")
        logger.info(f"   • Tiempo total: {elapsed_time/60:.2f} minutos")
        logger.info(f"   • Velocidad promedio: {updated/elapsed_time:.2f} respuestas/segundo")
        logger.info("=" * 70)
        
        # Verificar resultado
        cursor.execute("""
            SELECT COUNT(*) 
            FROM responses 
            WHERE bert_score IS NULL
        """)
        remaining_without_score = cursor.fetchone()[0]
        
        if remaining_without_score == 0:
            logger.info("🎉 ¡Todas las respuestas ahora tienen score!")
        else:
            logger.warning(f"⚠️  Aún quedan {remaining_without_score} respuestas sin score")
        
        # Mostrar estadísticas de scores
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                AVG(bert_score) as avg_score,
                MIN(bert_score) as min_score,
                MAX(bert_score) as max_score
            FROM responses
            WHERE bert_score IS NOT NULL
        """)
        
        total, avg_score, min_score, max_score = cursor.fetchone()
        
        logger.info("\n📈 ESTADÍSTICAS DE SCORES:")
        logger.info(f"   • Total con score: {total}")
        logger.info(f"   • Score promedio: {avg_score:.3f}")
        logger.info(f"   • Score mínimo: {min_score:.3f}")
        logger.info(f"   • Score máximo: {max_score:.3f}")
        
        # Distribución por rangos
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN bert_score < 0.50 THEN '0.0-0.5'
                    WHEN bert_score < 0.60 THEN '0.5-0.6'
                    WHEN bert_score < 0.70 THEN '0.6-0.7'
                    WHEN bert_score < 0.75 THEN '0.7-0.75 (Bajo umbral Flink)'
                    WHEN bert_score < 0.80 THEN '0.75-0.8'
                    WHEN bert_score < 0.90 THEN '0.8-0.9'
                    ELSE '0.9-1.0'
                END as score_range,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / {}, 1) as percentage
            FROM responses
            WHERE bert_score IS NOT NULL
            GROUP BY score_range
            ORDER BY score_range
        """.format(total))
        
        logger.info("\n📊 DISTRIBUCIÓN DE SCORES:")
        for score_range, count, percentage in cursor.fetchall():
            logger.info(f"   • {score_range}: {count} ({percentage}%)")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("🔄 SCRIPT DE ACTUALIZACIÓN DE BERT SCORES")
    logger.info("=" * 70)
    logger.info("Este script calculará BERTScore para todas las respuestas")
    logger.info("existentes en la base de datos que no tienen score asignado.")
    logger.info("")
    logger.info("⚠️  NOTA: Este proceso puede tardar varios minutos dependiendo")
    logger.info("   del número de respuestas sin score.")
    logger.info("=" * 70)
    
    try:
        update_scores_batch()
        logger.info("\n✅ Script finalizado exitosamente")
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Proceso interrumpido por el usuario")
        logger.info("   El progreso fue guardado. Puedes ejecutar el script nuevamente")
        logger.info("   para continuar desde donde se quedó.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ Error fatal: {e}")
        sys.exit(1)
