"""
Script para migrar backup de Tarea 1 al esquema de Tarea 2

Transformaciones:
- id → question_id (convertir a hash de 16 caracteres)
- question → question_text
- human_answer → original_answer
- llm_answer → llm_response
- score → bert_score (mantener valor)
- count → processing_attempts (mantener valor)
- created_at, updated_at (mantener)
- Agregar: total_processing_time_ms (simulado)
"""

import re
import hashlib
from datetime import datetime

def generate_question_id(original_id, question):
    """Genera un question_id de 16 caracteres basado en el ID original y la pregunta"""
    combined = f"{original_id}_{question}"
    hash_obj = hashlib.md5(combined.encode())
    return hash_obj.hexdigest()[:16]

def escape_sql_string(text):
    """Escapa comillas simples para SQL"""
    if text is None:
        return 'NULL'
    # Reemplazar comillas simples dobles por escapadas
    text = text.replace("''", "'")
    text = text.replace("'", "''")
    return f"'{text}'"

def parse_insert_line(line):
    """Parsea una línea INSERT de Tarea 1"""
    # Buscar el patrón VALUES (...)
    if "VALUES (" not in line:
        return None
    
    # Extraer solo la parte de valores
    start = line.find("VALUES (") + 8
    end = line.rfind(");")
    
    if start == -1 or end == -1:
        return None
    
    values_str = line[start:end]
    
    # Parsear campo por campo manejando comillas
    fields = []
    current = ""
    in_string = False
    i = 0
    
    while i < len(values_str):
        char = values_str[i]
        
        if char == "'" and (i == 0 or values_str[i-1] != "'"):
            in_string = not in_string
            current += char
        elif char == "," and not in_string:
            fields.append(current.strip())
            current = ""
        else:
            current += char
        
        i += 1
    
    # Agregar último campo
    if current.strip():
        fields.append(current.strip())
    
    if len(fields) != 8:
        return None
    
    # Extraer valores limpiando comillas
    def clean(s):
        s = s.strip()
        if s.startswith("'") and s.endswith("'"):
            return s[1:-1]
        return s
    
    return {
        'original_id': clean(fields[0]),
        'question': clean(fields[1]),
        'human_answer': clean(fields[2]),
        'llm_answer': clean(fields[3]),
        'score': clean(fields[4]),
        'count': clean(fields[5]),
        'created_at': clean(fields[6]),
        'updated_at': clean(fields[7])
    }

def transform_to_tarea2(record):
    """Transforma un registro de Tarea 1 a formato Tarea 2"""
    # Generar question_id único
    question_id = generate_question_id(record['original_id'], record['question'])
    
    # Calcular processing_time simulado (100-1500ms según intentos)
    attempts = int(record['count'])
    processing_time = 500 * attempts + (int(record['original_id']) % 500)
    
    # Construir INSERT para Tarea 2
    return (
        f"INSERT INTO public.responses "
        f"(question_id, question_text, llm_response, original_answer, bert_score, "
        f"processing_attempts, total_processing_time_ms, created_at, updated_at) "
        f"VALUES "
        f"('{question_id}', "
        f"{escape_sql_string(record['question'])}, "
        f"{escape_sql_string(record['llm_answer'])}, "
        f"{escape_sql_string(record['human_answer'])}, "
        f"{record['score']}, "
        f"{record['count']}, "
        f"{processing_time}, "
        f"'{record['created_at']}', "
        f"'{record['updated_at']}');"
    )

def main():
    input_file = "../dataset/backup_responses.sql"
    output_file = "../dataset/backup_responses_tarea2.sql"
    
    print("🔄 Iniciando migración de backup...")
    print(f"📂 Entrada: {input_file}")
    print(f"📂 Salida: {output_file}")
    
    processed = 0
    errors = 0
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as infile:
        with open(output_file, 'w', encoding='utf-8') as outfile:
            # Escribir encabezado
            outfile.write("-- Backup migrado de Tarea 1 a Tarea 2\n")
            outfile.write(f"-- Fecha de migración: {datetime.now()}\n")
            outfile.write("-- Esquema objetivo: responses (Tarea 2)\n\n")
            outfile.write("SET client_encoding = 'UTF8';\n")
            outfile.write("SET standard_conforming_strings = on;\n\n")
            
            for line in infile:
                line = line.strip()
                
                # Solo procesar líneas INSERT
                if not line.startswith("INSERT INTO public.responses"):
                    continue
                
                # Parsear registro
                record = parse_insert_line(line)
                if record is None:
                    errors += 1
                    continue
                
                # Transformar a Tarea 2
                try:
                    new_insert = transform_to_tarea2(record)
                    outfile.write(new_insert + "\n")
                    processed += 1
                    
                    if processed % 1000 == 0:
                        print(f"✅ Procesados: {processed} registros...")
                        
                except Exception as e:
                    print(f"❌ Error transformando registro {record.get('original_id', '?')}: {e}")
                    errors += 1
    
    print(f"\n🎉 Migración completada!")
    print(f"✅ Registros procesados: {processed}")
    print(f"❌ Errores: {errors}")
    print(f"📁 Archivo generado: {output_file}")
    
    return processed, errors

if __name__ == "__main__":
    main()
