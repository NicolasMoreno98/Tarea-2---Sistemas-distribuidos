#!/usr/bin/env python3
"""Script simple para migrar backup de Tarea 1 a Tarea 2"""

import sys
import hashlib

def create_question_id(text):
    """Genera un ID de 16 caracteres"""
    return hashlib.md5(text.encode()).hexdigest()[:16]

processed = 0
errors = 0

print("🔄 Procesando backup...")

with open("../dataset/backup_responses.sql", "r", encoding="utf-8", errors="replace") as f_in:
    with open("../dataset/backup_tarea2.sql", "w", encoding="utf-8") as f_out:
        # Escribir encabezado
        f_out.write("-- Backup migrado a esquema Tarea 2\n")
        f_out.write("SET client_encoding = 'UTF8';\n\n")
        
        for line_num, line in enumerate(f_in, 1):
            # Solo procesar líneas INSERT
            if not line.startswith("INSERT INTO public.responses"):
                continue
            
            try:
                # Extraer valores entre VALUES ( ... );
                if "VALUES (" not in line:
                    continue
                
                start_idx = line.find("VALUES (") + 8
                end_idx = line.rfind(");")
                
                if start_idx == -1 or end_idx == -1:
                    errors += 1
                    continue
                
                values = line[start_idx:end_idx]
                
                # Dividir valores (manejo básico de comillas)
                parts = []
                current = ""
                in_quote = False
                prev_char = ""
                
                for char in values:
                    if char == "'" and prev_char != "'":
                        in_quote = not in_quote
                    elif char == "," and not in_quote:
                        parts.append(current.strip())
                        current = ""
                        prev_char = char
                        continue
                    
                    current += char
                    prev_char = char
                
                if current:
                    parts.append(current.strip())
                
                # Debe tener 8 campos (Tarea 1)
                if len(parts) != 8:
                    errors += 1
                    continue
                
                id_val, question, human_ans, llm_ans, score, count, created, updated = parts
                
                # Limpiar comillas
                question_clean = question.strip("'")
                
                # Generar question_id
                qid = create_question_id(id_val.strip("'") + question_clean)
                
                # Calcular processing_time simulado
                try:
                    attempts = int(count)
                    proc_time = 500 * attempts
                except:
                    attempts = 1
                    proc_time = 500
                
                # Construir nuevo INSERT para Tarea 2
                new_line = (
                    f"INSERT INTO public.responses "
                    f"(question_id, question_text, llm_response, original_answer, "
                    f"bert_score, processing_attempts, total_processing_time_ms, "
                    f"created_at, updated_at) "
                    f"VALUES "
                    f"('{qid}', {question}, {llm_ans}, {human_ans}, {score}, {count}, "
                    f"{proc_time}, {created}, {updated});\n"
                )
                
                f_out.write(new_line)
                processed += 1
                
                if processed % 1000 == 0:
                    print(f"✅ Procesados: {processed}")
                
            except Exception as e:
                errors += 1
                if errors < 10:
                    print(f"❌ Error línea {line_num}: {e}")

print(f"\n🎉 Completado!")
print(f"✅ Migrados: {processed}")
print(f"❌ Errores: {errors}")
