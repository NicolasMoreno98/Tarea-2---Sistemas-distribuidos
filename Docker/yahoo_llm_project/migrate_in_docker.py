"""
Script para migrar datos desde response.json a PostgreSQL
Versión simplificada para ejecutar en Docker
"""

import json
import psycopg2
import hashlib
from datetime import datetime
import random

# Configuración de conexión (dentro de Docker)
DATABASE_URL = "postgresql://user:password@postgres:5432/yahoo_db"

def generate_question_id(question_text):
    """Generar ID único basado en hash del texto"""
    return hashlib.sha256(question_text.encode('utf-8')).hexdigest()[:16]

def migrate_data():
    """Migrar datos de response.json a PostgreSQL"""
    
    # Conectar a base de datos
    print("Conectando a PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    print("✓ Conectado a PostgreSQL")
    
    # Leer response.json
    print("Leyendo response.json...")
    with open('/data/response.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # El archivo tiene estructura con summary y responses
    if isinstance(data, dict) and 'responses' in data:
        responses = data['responses']
    else:
        responses = data
        
    print(f"✓ Leídos {len(responses)} registros")
    
    # Migrar datos
    inserted = 0
    skipped = 0
    
    print("\nMigrando datos...")
    for i, resp in enumerate(responses):
        try:
            # El formato tiene 'question' y 'llm_answer' o 'human_answer'
            question_text = resp.get('question')
            answer = resp.get('llm_answer') or resp.get('human_answer')
            original_answer = resp.get('human_answer') if resp.get('llm_answer') else None
            
            if not question_text or not answer:
                skipped += 1
                continue
            
            question_id = generate_question_id(question_text)
            
            # Simular métricas del pipeline
            bert_score = round(random.uniform(0.75, 0.95), 2)
            processing_attempts = random.choice([1, 1, 1, 2, 2, 3])  # Mayoría 1 intento
            latency_ms = random.randint(1500, 4000)
            
            cursor.execute(
                """
                INSERT INTO responses (
                    question_id, question_text, llm_response, original_answer,
                    bert_score, processing_attempts, total_processing_time_ms, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (question_id) DO NOTHING
                """,
                (
                    question_id,
                    question_text,
                    answer,
                    original_answer,
                    bert_score,
                    processing_attempts,
                    latency_ms,
                    datetime.utcnow()
                )
            )
            
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
            
            # Commit cada 100 registros
            if (i + 1) % 100 == 0:
                conn.commit()
                print(f"  Procesados {i + 1}/{len(responses)} registros...")
                
        except Exception as e:
            print(f"  ✗ Error en registro {i}: {e}")
            conn.rollback()
            continue
    
    # Commit final
    conn.commit()
    
    print(f"\n✓ Migración completada:")
    print(f"  - Insertados: {inserted}")
    print(f"  - Omitidos: {skipped}")
    print(f"  - Total: {len(responses)}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    try:
        migrate_data()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        exit(1)
