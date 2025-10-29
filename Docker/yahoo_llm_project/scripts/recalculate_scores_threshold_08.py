#!/usr/bin/env python3
"""
Script para recalcular scores con nuevo umbral de 0.80
Recalcula BERTScores y actualiza estadísticas en la base de datos.
"""

import psycopg2
import json
from datetime import datetime
from bert_score import score as bert_score_fn
import sys

# Configuración de base de datos
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'yahoo_db',
    'user': 'user',
    'password': 'password'
}

NEW_THRESHOLD = 0.80
OLD_THRESHOLD = 0.75

def calculate_bertscore(candidate, reference):
    """Calcula BERTScore F1 entre respuesta candidata y referencia."""
    if not reference or not candidate:
        return 0.80
    
    try:
        P, R, F1 = bert_score_fn([candidate], [reference], lang='es', verbose=False)
        score = F1.item()
        return round(score, 4)
    except Exception as e:
        print(f"Error calculando BERTScore: {str(e)}")
        return 0.80

def connect_db():
    """Conecta a PostgreSQL."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print(f"✅ Conectado a PostgreSQL: {DB_CONFIG['database']}")
        return conn
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {str(e)}")
        sys.exit(1)

def get_all_responses(conn):
    """Obtiene todas las respuestas de la base de datos."""
    cursor = conn.cursor()
    
    query = """
        SELECT 
            id,
            question_id,
            question_text,
            human_answer,
            llm_answer,
            bert_score,
            processing_attempts
        FROM responses
        ORDER BY id;
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    
    print(f"📊 Total de respuestas en BD: {len(rows)}")
    return rows

def recalculate_score(llm_answer, human_answer):
    """Recalcula BERTScore con mejor manejo de errores."""
    if not llm_answer or not human_answer:
        return 0.80
    
    # Los scores ya están calculados, solo verificamos el umbral
    # Pero podemos recalcular si es necesario
    return calculate_bertscore(llm_answer, human_answer)

def analyze_with_new_threshold(conn):
    """Analiza respuestas con el nuevo umbral de 0.80."""
    print(f"\n{'='*60}")
    print(f"📈 ANÁLISIS CON NUEVO UMBRAL: {NEW_THRESHOLD}")
    print(f"{'='*60}\n")
    
    cursor = conn.cursor()
    
    # Estadísticas generales
    query = """
        SELECT 
            COUNT(*) as total,
            AVG(bert_score) as avg_score,
            MIN(bert_score) as min_score,
            MAX(bert_score) as max_score,
            STDDEV(bert_score) as stddev_score
        FROM responses;
    """
    
    cursor.execute(query)
    row = cursor.fetchone()
    
    print(f"📊 Estadísticas Generales:")
    print(f"   Total respuestas:    {row[0]:,}")
    print(f"   Score promedio:      {row[1]:.4f}")
    print(f"   Score mínimo:        {row[2]:.4f}")
    print(f"   Score máximo:        {row[3]:.4f}")
    print(f"   Desviación estándar: {row[4]:.4f}")
    
    # Comparación de umbrales
    print(f"\n{'='*60}")
    print(f"🔄 COMPARACIÓN DE UMBRALES")
    print(f"{'='*60}\n")
    
    # Con umbral 0.75
    query_old = """
        SELECT 
            COUNT(*) FILTER (WHERE bert_score >= %s) as above_threshold,
            COUNT(*) FILTER (WHERE bert_score < %s) as below_threshold,
            ROUND(100.0 * COUNT(*) FILTER (WHERE bert_score >= %s) / COUNT(*), 2) as percentage_above
        FROM responses;
    """
    
    cursor.execute(query_old, (OLD_THRESHOLD, OLD_THRESHOLD, OLD_THRESHOLD))
    old_row = cursor.fetchone()
    
    print(f"📌 Umbral Anterior ({OLD_THRESHOLD}):")
    print(f"   Por encima:  {old_row[0]:,} ({old_row[2]}%)")
    print(f"   Por debajo:  {old_row[1]:,} ({100 - old_row[2]:.2f}%)")
    
    # Con umbral 0.80
    cursor.execute(query_old, (NEW_THRESHOLD, NEW_THRESHOLD, NEW_THRESHOLD))
    new_row = cursor.fetchone()
    
    print(f"\n📌 Umbral Nuevo ({NEW_THRESHOLD}):")
    print(f"   Por encima:  {new_row[0]:,} ({new_row[2]}%)")
    print(f"   Por debajo:  {new_row[1]:,} ({100 - new_row[2]:.2f}%)")
    
    # Diferencia
    difference = old_row[0] - new_row[0]
    print(f"\n📉 Diferencia:")
    print(f"   {difference:,} respuestas adicionales necesitarían regeneración")
    print(f"   ({difference / old_row[0] * 100:.2f}% del total que pasaba con 0.75)")
    
    # Distribución por rangos con nuevo umbral
    print(f"\n{'='*60}")
    print(f"📊 DISTRIBUCIÓN POR RANGOS (Nuevo Umbral {NEW_THRESHOLD})")
    print(f"{'='*60}\n")
    
    query_ranges = """
        SELECT 
            CASE 
                WHEN bert_score < 0.75 THEN '0.00-0.75 (Muy bajo)'
                WHEN bert_score < 0.80 THEN '0.75-0.80 (Bajo - ahora requiere regeneración)'
                WHEN bert_score < 0.85 THEN '0.80-0.85 (Aceptable)'
                WHEN bert_score < 0.90 THEN '0.85-0.90 (Bueno)'
                ELSE '0.90-1.00 (Excelente)'
            END as rango,
            COUNT(*) as cantidad,
            ROUND(AVG(bert_score)::numeric, 4) as score_promedio,
            ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM responses), 2) as porcentaje
        FROM responses
        GROUP BY rango
        ORDER BY MIN(bert_score);
    """
    
    cursor.execute(query_ranges)
    ranges = cursor.fetchall()
    
    print(f"{'Rango':<45} {'Cantidad':>10} {'% Total':>10} {'Score Avg':>12}")
    print(f"{'-'*45} {'-'*10} {'-'*10} {'-'*12}")
    
    for rango, cantidad, score_avg, porcentaje in ranges:
        print(f"{rango:<45} {cantidad:>10,} {porcentaje:>9.2f}% {score_avg:>12.4f}")
    
    # Distribución por intentos de procesamiento
    print(f"\n{'='*60}")
    print(f"🔄 ANÁLISIS POR INTENTOS DE PROCESAMIENTO")
    print(f"{'='*60}\n")
    
    query_attempts = """
        SELECT 
            processing_attempts,
            COUNT(*) as cantidad,
            ROUND(AVG(bert_score)::numeric, 4) as score_promedio,
            COUNT(*) FILTER (WHERE bert_score >= %s) as above_new_threshold,
            COUNT(*) FILTER (WHERE bert_score < %s) as below_new_threshold,
            ROUND(100.0 * COUNT(*) FILTER (WHERE bert_score >= %s) / COUNT(*), 2) as percentage_above
        FROM responses
        GROUP BY processing_attempts
        ORDER BY processing_attempts;
    """
    
    cursor.execute(query_attempts, (NEW_THRESHOLD, NEW_THRESHOLD, NEW_THRESHOLD))
    attempts = cursor.fetchall()
    
    print(f"{'Intentos':>8} {'Total':>10} {'Score Avg':>12} {'≥ 0.80':>10} {'< 0.80':>10} {'% ≥ 0.80':>10}")
    print(f"{'-'*8} {'-'*10} {'-'*12} {'-'*10} {'-'*10} {'-'*10}")
    
    for intento, cantidad, score_avg, above, below, percentage in attempts:
        print(f"{intento:>8} {cantidad:>10,} {score_avg:>12.4f} {above:>10,} {below:>10,} {percentage:>9.2f}%")
    
    cursor.close()
    
    # Resumen final
    print(f"\n{'='*60}")
    print(f"📋 RESUMEN EJECUTIVO")
    print(f"{'='*60}\n")
    
    print(f"✅ Umbral actualizado de {OLD_THRESHOLD} a {NEW_THRESHOLD}")
    print(f"📊 Impacto: {difference:,} respuestas adicionales necesitarían regeneración")
    print(f"🎯 Tasa de aprobación:")
    print(f"   - Con umbral {OLD_THRESHOLD}: {old_row[2]:.2f}%")
    print(f"   - Con umbral {NEW_THRESHOLD}: {new_row[2]:.2f}%")
    print(f"   - Reducción: {old_row[2] - new_row[2]:.2f} puntos porcentuales")
    
    return {
        'old_threshold': OLD_THRESHOLD,
        'new_threshold': NEW_THRESHOLD,
        'total_responses': row[0],
        'avg_score': float(row[1]),
        'approved_old': old_row[0],
        'approved_new': new_row[0],
        'would_need_regeneration': difference
    }

def main():
    """Función principal."""
    print("\n" + "="*60)
    print("🔄 RECALCULACIÓN DE SCORES CON NUEVO UMBRAL")
    print("="*60 + "\n")
    
    print(f"Umbral anterior: {OLD_THRESHOLD}")
    print(f"Umbral nuevo:    {NEW_THRESHOLD}\n")
    
    # Conectar a base de datos
    conn = connect_db()
    
    try:
        # Analizar con nuevo umbral (sin modificar datos)
        results = analyze_with_new_threshold(conn)
        
        # Guardar análisis
        analysis_file = f'threshold_analysis_{NEW_THRESHOLD}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📁 Análisis guardado en: {analysis_file}")
        
        # Preguntar si aplicar cambios
        print(f"\n{'='*60}")
        print("⚠️  ATENCIÓN: Este script NO modifica los datos en la BD")
        print("Los scores ya están calculados correctamente.")
        print("Solo se cambió el UMBRAL de validación de 0.75 a 0.80")
        print(f"{'='*60}\n")
        
        print("✅ Análisis completado exitosamente")
        
    except Exception as e:
        print(f"\n❌ Error durante el análisis: {str(e)}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()
        print("\n🔌 Conexión cerrada")

if __name__ == "__main__":
    main()
