"""
Script para Popular Base de Datos desde response.json
Tarea 2 - Sistemas Distribuidos

Este script migra los datos de response.json (Tarea 1) a la nueva estructura
de PostgreSQL (Tarea 2), simulando que ya fueron procesados por el pipeline.

Esto permite:
1. Demostrar el sistema funcionando sin esperar 5+ horas
2. Tener datos históricos para análisis comparativo
3. Enfocar la demo en casos nuevos y manejo de errores
"""

import json
import psycopg2
import hashlib
from datetime import datetime
import sys

# Configuración de conexión
DATABASE_URL = "postgresql://user:password@localhost:5432/yahoo_db"

def generate_question_id(question_text):
    """Generar ID único basado en hash del texto"""
    return hashlib.sha256(question_text.encode('utf-8')).hexdigest()[:16]

def migrate_response_data(response_json_path):
    """Migrar datos de response.json a PostgreSQL Tarea 2"""
    
    # Conectar a base de datos
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        print(f"✓ Conectado a PostgreSQL")
    except Exception as e:
        print(f"✗ Error conectando a PostgreSQL: {e}")
        sys.exit(1)
    
    # Leer response.json
    try:
        with open(response_json_path, 'r', encoding='utf-8') as f:
            responses = json.load(f)
        print(f"✓ Leídos {len(responses)} registros de {response_json_path}")
    except Exception as e:
        print(f"✗ Error leyendo JSON: {e}")
        sys.exit(1)
    
    # Migrar datos
    inserted = 0
    skipped = 0
    
    for idx, response in enumerate(responses, 1):
        try:
            # Extraer datos del formato Tarea 1
            question_text = response.get('question', '')
            llm_response = response.get('llm_answer', response.get('llm_response', ''))
            original_answer = response.get('human_answer', response.get('original_answer', ''))
            bert_score = response.get('bert_score', response.get('score'))
            
            # Generar question_id consistente
            question_id = generate_question_id(question_text)
            
            # Insertar en tabla responses (formato Tarea 2)
            cursor.execute("""
                INSERT INTO responses (
                    question_id, question_text, llm_response, original_answer,
                    bert_score, processing_attempts, total_processing_time_ms, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (question_id) DO UPDATE SET
                    bert_score = EXCLUDED.bert_score,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                question_id,
                question_text,
                llm_response,
                original_answer,
                float(bert_score) if bert_score else None,
                1,  # processing_attempts (asumimos primera vez)
                2000,  # total_processing_time_ms (valor típico)
                datetime.utcnow()
            ))
            
            # También insertar en score_history para análisis
            if bert_score:
                cursor.execute("""
                    INSERT INTO score_history (
                        question_id, attempt_number, bert_score, 
                        processing_time_ms, timestamp
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    question_id,
                    1,
                    float(bert_score),
                    2000,
                    datetime.utcnow()
                ))
            
            inserted += 1
            
            # Commit cada 100 registros
            if idx % 100 == 0:
                conn.commit()
                print(f"  Progreso: {idx}/{len(responses)} registros procesados...")
            
        except Exception as e:
            print(f"  ⚠ Warning: Error en registro {idx}: {e}")
            skipped += 1
            continue
    
    # Commit final
    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n" + "="*60)
    print(f"✓ Migración completada:")
    print(f"  - Insertados: {inserted}")
    print(f"  - Omitidos: {skipped}")
    print(f"  - Total: {len(responses)}")
    print("="*60)

def generate_sample_queries(num_samples=10):
    """Generar algunas preguntas de ejemplo que NO están en la BD"""
    samples = [
        {
            "question_text": "What is the best way to learn Python in 2025?",
            "original_answer": "Start with interactive tutorials, practice daily, build projects, and join online communities."
        },
        {
            "question_text": "How do I fix a slow computer?",
            "original_answer": "Clean up disk space, disable startup programs, update drivers, scan for malware, and add more RAM if needed."
        },
        {
            "question_text": "What causes climate change?",
            "original_answer": "Primarily greenhouse gas emissions from burning fossil fuels, deforestation, and industrial activities."
        },
        {
            "question_text": "How does blockchain technology work?",
            "original_answer": "It uses distributed ledger technology with cryptographic hashing to create an immutable chain of transaction blocks."
        },
        {
            "question_text": "What are the symptoms of vitamin D deficiency?",
            "original_answer": "Fatigue, bone pain, muscle weakness, mood changes, and frequent infections."
        },
        {
            "question_text": "How do I start a small business?",
            "original_answer": "Create a business plan, secure funding, register your business, set up accounting, and market your products/services."
        },
        {
            "question_text": "What is the difference between AI and machine learning?",
            "original_answer": "AI is the broader concept of machines mimicking human intelligence, while machine learning is a subset focused on learning from data."
        },
        {
            "question_text": "How can I improve my credit score?",
            "original_answer": "Pay bills on time, reduce credit utilization, keep old accounts open, and dispute errors on your credit report."
        },
        {
            "question_text": "What is quantum computing?",
            "original_answer": "Computing technology that uses quantum mechanics principles like superposition and entanglement to perform calculations."
        },
        {
            "question_text": "How do solar panels work?",
            "original_answer": "They convert sunlight into electricity using photovoltaic cells made of semiconductor materials."
        }
    ]
    
    # Guardar como JSON
    output_file = "sample_new_questions.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(samples[:num_samples], f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Generadas {num_samples} preguntas de ejemplo en: {output_file}")
    print("  Usa estas preguntas para demostrar el pipeline asíncrono en acción")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  MIGRACIÓN DE DATOS: Tarea 1 → Tarea 2")
    print("="*60 + "\n")
    
    # Ruta al archivo response.json
    response_json_path = input("Ruta a response.json (Enter para default): ").strip()
    if not response_json_path:
        response_json_path = r"D:\U\Sistemas Distribuidos\Respaldo\dataset\response.json"
    
    print(f"\nUsando archivo: {response_json_path}\n")
    
    # Migrar datos
    migrate_response_data(response_json_path)
    
    # Generar preguntas de ejemplo
    generate_sample_queries(10)
    
    print("\n✓ Todo listo para demostrar Tarea 2!")
    print("\nPróximos pasos:")
    print("  1. Usa las preguntas en sample_new_questions.json para tu demo")
    print("  2. Estas preguntas pasarán por el pipeline completo Kafka→Flink")
    print("  3. Los 10,000 registros migrados sirven como datos históricos")
    print("  4. Puedes comparar métricas: Tarea 1 vs Tarea 2\n")
