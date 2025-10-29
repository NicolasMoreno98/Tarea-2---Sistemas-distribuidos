#!/usr/bin/env python3
"""
Script para generar SQL de migración desde response.json

Genera un archivo .sql que puede ser ejecutado directamente en PostgreSQL
"""

import json
import hashlib
from datetime import datetime

def generate_question_id(question_id_original, question_text):
    """Genera un question_id único de 16 caracteres"""
    combined = f"{question_id_original}_{question_text}"
    return hashlib.md5(combined.encode()).hexdigest()[:16]

def determine_processing_attempts(score):
    """Determina el número de intentos basándose en el score"""
    if score >= 0.90:
        return 1
    elif score >= 0.80:
        return 2
    else:
        return 3

def calculate_processing_time(attempts, score):
    """Calcula tiempo de procesamiento simulado"""
    base_time = 500 * attempts
    score_penalty = int((1.0 - score) * 1000)
    return base_time + score_penalty

def escape_sql(text):
    """Escapa texto para SQL"""
    if text is None:
        return ''
    return text.replace("'", "''").replace("\\", "\\\\")

def generate_sql():
    """Genera archivo SQL con los INSERT statements"""
    
    print("Generando SQL de migración desde response.json...")
    
    # Leer JSON
    with open('../response.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    responses = data.get('responses', [])
    print(f"Total de respuestas: {len(responses)}")
    
    # Abrir archivo SQL de salida
    with open('../dataset/migrate_from_json.sql', 'w', encoding='utf-8') as f:
        # Encabezado
        f.write("-- Migración desde response.json al esquema Tarea 2\n")
        f.write(f"-- Generado: {datetime.now()}\n")
        f.write(f"-- Total de registros: {len(responses)}\n\n")
        f.write("SET client_encoding = 'UTF8';\n")
        f.write("BEGIN;\n\n")
        
        processed = 0
        errors = 0
        
        for idx, response in enumerate(responses, 1):
            try:
                # Extraer datos
                question_id_orig = response.get('question_id', str(idx))
                question = escape_sql(response.get('question', ''))
                human_answer = escape_sql(response.get('human_answer', ''))
                llm_answer = escape_sql(response.get('llm_answer', ''))
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
                
                # Generar INSERT
                insert = f"""INSERT INTO responses (question_id, question_text, llm_response, original_answer, bert_score, processing_attempts, total_processing_time_ms, created_at, updated_at) VALUES ('{qid}', '{question}', '{llm_answer}', '{human_answer}', {score}, {attempts}, {proc_time}, '{created_at}', '{updated_at}') ON CONFLICT (question_id) DO NOTHING;\n"""
                
                f.write(insert)
                processed += 1
                
                if processed % 1000 == 0:
                    print(f"Procesados: {processed}/{len(responses)}")
            
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"ERROR en registro {idx}: {e}")
        
        f.write("\nCOMMIT;\n")
        f.write(f"\n-- Registros procesados: {processed}\n")
        f.write(f"-- Errores: {errors}\n")
    
    print(f"\nSQL generado: ../dataset/migrate_from_json.sql")
    print(f"Registros: {processed}")
    print(f"Errores: {errors}")
    return processed

if __name__ == "__main__":
    generate_sql()
