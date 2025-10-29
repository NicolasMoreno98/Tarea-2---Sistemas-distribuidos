#!/usr/bin/env python3
"""
Script para migrar datos de response.json a PostgreSQL con esquema Tarea 2

Estrategia:
- Lee las 7,915 respuestas únicas del JSON
- Usa el BERTScore existente (campo 'score')
- Asigna processing_attempts basándose en el score:
  * score >= 0.90 → 1 intento (excelente al primer intento)
  * 0.80 <= score < 0.90 → 2 intentos (mejorada tras 1 regeneración)
  * score < 0.80 → 3 intentos (requirió máximo de regeneraciones)
- Inserta directamente en PostgreSQL
"""

import json
import psycopg2
import hashlib
from datetime import datetime
import sys

# Configuración PostgreSQL (ejecutándose en el mismo contenedor)
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'yahoo_db',
    'user': 'user',
    'password': 'password'
}

def generate_question_id(question_id_original, question_text):
    """Genera un question_id único de 16 caracteres"""
    combined = f"{question_id_original}_{question_text}"
    return hashlib.md5(combined.encode()).hexdigest()[:16]

def determine_processing_attempts(score):
    """
    Determina el número de intentos basándose en el score
    
    Lógica:
    - Scores altos (>=0.90): exitosos al primer intento
    - Scores medios (0.80-0.89): necesitaron 1 regeneración
    - Scores bajos (<0.80): necesitaron 2 regeneraciones (3 intentos totales)
    """
    if score >= 0.90:
        return 1
    elif score >= 0.80:
        return 2
    else:
        return 3

def calculate_processing_time(attempts, score):
    """
    Calcula tiempo de procesamiento simulado
    
    - Base: 500ms por intento
    - Variación basada en score (scores más bajos → más tiempo)
    """
    base_time = 500 * attempts
    score_penalty = int((1.0 - score) * 1000)  # Hasta 1000ms extra para scores bajos
    return base_time + score_penalty

def migrate_data():
    """Migra datos del JSON a PostgreSQL"""
    
    print("=" * 60)
    print("MIGRACION DE DATOS: response.json -> PostgreSQL")
    print("=" * 60)
    
    # Leer JSON
    print("\n[1/5] Leyendo response.json...")
    try:
        with open('/tmp/response.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: No se pudo leer response.json: {e}")
        return 1
    
    responses = data.get('responses', [])
    total_responses = len(responses)
    unique_questions = data.get('summary', {}).get('unique_questions', 0)
    
    print(f"   Total de respuestas en JSON: {total_responses}")
    print(f"   Preguntas únicas reportadas: {unique_questions}")
    
    # Conectar a PostgreSQL
    print("\n[2/5] Conectando a PostgreSQL...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("   Conexión exitosa")
    except Exception as e:
        print(f"ERROR: No se pudo conectar a PostgreSQL: {e}")
        print("   Verifica que el contenedor postgres_db esté corriendo")
        return 1
    
    # Verificar tabla actual
    print("\n[3/5] Verificando estado actual de la base de datos...")
    try:
        cursor.execute("SELECT COUNT(*) FROM responses;")
        current_count = cursor.fetchone()[0]
        print(f"   Registros actuales: {current_count}")
        
        if current_count > 0:
            response = input(f"\n   ⚠️  Ya hay {current_count} registros. ¿Limpiar tabla? (s/N): ")
            if response.lower() == 's':
                cursor.execute("TRUNCATE TABLE responses CASCADE;")
                conn.commit()
                print("   Tabla limpiada")
            else:
                print("   Manteniendo registros existentes (puede haber duplicados)")
    except Exception as e:
        print(f"ERROR verificando tabla: {e}")
        conn.close()
        return 1
    
    # Procesar e insertar datos
    print("\n[4/5] Procesando y migrando datos...")
    
    inserted = 0
    duplicates = 0
    errors = 0
    
    # Preparar statement INSERT
    insert_query = """
        INSERT INTO responses (
            question_id, question_text, llm_response, original_answer,
            bert_score, processing_attempts, total_processing_time_ms,
            created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON CONFLICT (question_id) DO NOTHING;
    """
    
    # Procesar en lotes para eficiencia
    batch_size = 500
    batch = []
    
    for idx, response in enumerate(responses, 1):
        try:
            # Extraer datos
            question_id_orig = response.get('question_id', str(idx))
            question = response.get('question', '')
            human_answer = response.get('human_answer', '')
            llm_answer = response.get('llm_answer', '')
            score = response.get('score', 0.0)
            timestamp = response.get('timestamp', datetime.now().timestamp())
            
            # Validar datos mínimos
            if not question or not llm_answer:
                errors += 1
                continue
            
            # Generar campos calculados
            qid = generate_question_id(question_id_orig, question)
            attempts = determine_processing_attempts(score)
            proc_time = calculate_processing_time(attempts, score)
            
            # Convertir timestamp a datetime
            created_at = datetime.fromtimestamp(timestamp)
            updated_at = created_at
            
            # Agregar a batch
            batch.append((
                qid,
                question,
                llm_answer,
                human_answer,
                score,
                attempts,
                proc_time,
                created_at,
                updated_at
            ))
            
            # Ejecutar batch cuando alcance el tamaño
            if len(batch) >= batch_size:
                cursor.executemany(insert_query, batch)
                conn.commit()
                inserted += len(batch)
                batch = []
                
                print(f"   Progreso: {inserted}/{total_responses} registros migrados...", end='\r')
        
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"\n   ERROR en registro {idx}: {e}")
    
    # Insertar batch final
    if batch:
        try:
            cursor.executemany(insert_query, batch)
            conn.commit()
            inserted += len(batch)
        except Exception as e:
            print(f"\n   ERROR en batch final: {e}")
    
    print(f"\n   Migración de datos completada")
    
    # Verificar resultados
    print("\n[5/5] Verificando resultados...")
    try:
        # Contar registros finales
        cursor.execute("SELECT COUNT(*) FROM responses;")
        final_count = cursor.fetchone()[0]
        
        # Estadísticas de scores
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                ROUND(AVG(bert_score)::numeric, 3) as avg_score,
                ROUND(MIN(bert_score)::numeric, 3) as min_score,
                ROUND(MAX(bert_score)::numeric, 3) as max_score,
                ROUND(STDDEV(bert_score)::numeric, 3) as stddev_score
            FROM responses;
        """)
        stats = cursor.fetchone()
        
        # Distribución por intentos
        cursor.execute("""
            SELECT 
                processing_attempts,
                COUNT(*) as count,
                ROUND(AVG(bert_score)::numeric, 3) as avg_score,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM responses), 1) as percentage
            FROM responses
            GROUP BY processing_attempts
            ORDER BY processing_attempts;
        """)
        attempts_dist = cursor.fetchall()
        
        print(f"\n   Registros en base de datos: {final_count}")
        print(f"\n   Estadísticas de BERTScore:")
        print(f"      Total: {stats[0]}")
        print(f"      Promedio: {stats[1]}")
        print(f"      Mínimo: {stats[2]}")
        print(f"      Máximo: {stats[3]}")
        print(f"      Desviación: {stats[4]}")
        
        print(f"\n   Distribución por intentos de procesamiento:")
        print(f"      {'Intentos':<10} {'Cantidad':<10} {'Score Prom.':<15} {'Porcentaje'}")
        print(f"      {'-'*10} {'-'*10} {'-'*15} {'-'*10}")
        for row in attempts_dist:
            print(f"      {row[0]:<10} {row[1]:<10} {row[2]:<15} {row[3]}%")
        
    except Exception as e:
        print(f"   ERROR verificando resultados: {e}")
    
    # Cerrar conexión
    cursor.close()
    conn.close()
    
    # Resumen final
    print("\n" + "=" * 60)
    print("RESUMEN DE MIGRACION")
    print("=" * 60)
    print(f"Registros procesados: {total_responses}")
    print(f"Registros insertados: {inserted}")
    print(f"Duplicados omitidos: {total_responses - inserted - errors}")
    print(f"Errores: {errors}")
    print(f"\nRegistros finales en BD: {final_count}")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = migrate_data()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nMigración cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
