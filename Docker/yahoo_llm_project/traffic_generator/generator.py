import pandas as pd
import requests
import json
import random
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

API_URL = "http://storage-service:5001/query"
CSV_FILE = "/data/train.csv"
OUTPUT_FILE = "/data/response.json"
CACHED_IDS_FILE = "/data/cached_question_ids.txt"
NUM_REQUESTS = 100  # Número de requests a generar
USE_CACHED_IDS = os.getenv('USE_CACHED_IDS', 'false').lower() == 'true'

def load_cached_ids():
    """Cargar los IDs de preguntas que ya están en cache/DB"""
    try:
        with open(CACHED_IDS_FILE, 'r') as f:
            ids = [int(line.strip()) for line in f if line.strip()]
        print(f"✓ Cargados {len(ids)} IDs de preguntas cacheadas")
        return ids
    except Exception as e:
        print(f"✗ Error cargando cached IDs: {e}")
        return []

def load_questions():
    try:
        print("Cargando dataset...")
        
        if USE_CACHED_IDS:
            # Cargar solo las preguntas que ya están en cache
            cached_ids = load_cached_ids()
            if not cached_ids:
                print("⚠ No se encontraron IDs cacheados, cargando primeras 20k preguntas")
                df = pd.read_csv(CSV_FILE, nrows=20000)
            else:
                # Cargar todo el CSV y filtrar por los IDs cacheados
                print(f"📥 Cargando train.csv completo para obtener preguntas cacheadas...")
                df = pd.read_csv(CSV_FILE)
                # Filtrar solo las filas con índices en cached_ids (ajustando por 0-index)
                cached_indices = [idx - 1 for idx in cached_ids if idx > 0]
                df = df.iloc[cached_indices]
                print(f"✓ Filtradas {len(df)} preguntas de la cache")
        else:
            # Comportamiento original: primeras 20k preguntas
            df = pd.read_csv(CSV_FILE, nrows=20000)
        
        questions = []
        for idx, row in df.iterrows():
            questions.append({
                'id': str(idx + 1),
                'question': str(row.iloc[1]),
                'best_answer': str(row.iloc[3]) if pd.notna(row.iloc[3]) else ""
            })
        
        print(f"Cargadas {len(questions)} preguntas")
        return questions
        
    except Exception as e:
        print(f"Error cargando questions: {e}")
        return []

def send_request(question_data, max_retries=2):
    """
    Envía request al storage-service y maneja respuestas asíncronas
    """
    # Preparar payload en el formato que espera storage-service
    payload = {
        'question_text': question_data['question'],
        'original_answer': question_data['best_answer']
    }
    
    for attempt in range(max_retries):
        try:
            print(f"    Intento {attempt + 1}/{max_retries}")
            response = requests.post(API_URL, json=payload, timeout=10)
            
            if response.status_code == 200:
                # Respuesta encontrada (cache o database)
                result = response.json()
                response_data = result.get('result', {})
                
                return {
                    'question_id': question_data['id'],
                    'question': question_data['question'],
                    'human_answer': question_data['best_answer'],
                    'llm_answer': response_data.get('llm_response', ''),
                    'source': result.get('source', 'unknown'),
                    'score': response_data.get('bert_score', 0.0),
                    'timestamp': time.time(),
                    'processing_attempts': response_data.get('processing_attempts', 1)
                }
                
            elif response.status_code == 202:
                # Respuesta pendiente - necesita procesamiento asíncrono
                result = response.json()
                question_id = result.get('question_id')
                print(f"    Pregunta en procesamiento asíncrono (ID: {question_id})")
                
                # Polling para esperar resultado (máximo 60 segundos)
                max_polls = 60
                poll_interval = 1
                
                for poll_attempt in range(max_polls):
                    time.sleep(poll_interval)
                    status_url = f"http://storage-service:5001/status/{question_id}"
                    
                    try:
                        status_response = requests.get(status_url, timeout=5)
                        
                        if status_response.status_code == 200:
                            status_result = status_response.json()
                            response_data = status_result.get('result', {})
                            
                            print(f"    ✓ Procesamiento completado después de {poll_attempt + 1}s")
                            return {
                                'question_id': question_data['id'],
                                'question': question_data['question'],
                                'human_answer': question_data['best_answer'],
                                'llm_answer': response_data.get('llm_response', ''),
                                'source': 'async_processed',
                                'score': response_data.get('bert_score', 0.0),
                                'timestamp': time.time(),
                                'processing_attempts': response_data.get('processing_attempts', 1),
                                'wait_time': poll_attempt + 1
                            }
                    except Exception as poll_error:
                        print(f"    Error en polling: {poll_error}")
                        continue
                
                print(f"    Timeout esperando procesamiento asíncrono")
                return None
                
            elif response.status_code == 429:
                print(f"    Rate limit alcanzado, esperando...")
                wait_time = 60
                print(f"    Esperando {wait_time} segundos por rate limit...")
                time.sleep(wait_time)
                continue
            else:
                print(f"    Error {response.status_code}: {response.text[:200]}")
                
        except requests.exceptions.Timeout:
            print(f"    Timeout después de 10 segundos")
        except Exception as e:
            print(f"    Excepción: {e}")
        
        if attempt < max_retries - 1:
            wait_time = 10 + (attempt * 5)
            print(f"    Esperando {wait_time} segundos antes del siguiente intento...")
            time.sleep(wait_time)
    
    print(f"    Falló después de {max_retries} intentos")
    return None

def main():
    print("Yahoo LLM Traffic Generator")
    print()
    questions = load_questions()
    if not questions:
        print("No se pudieron cargar las preguntas")
        return
    
    print(f"Seleccionando {NUM_REQUESTS} preguntas aleatorias con repetición...")
    selected_questions = random.choices(questions, k=NUM_REQUESTS)
    
    unique_ids = set(q['id'] for q in selected_questions)
    print(f"Preguntas únicas seleccionadas: {len(unique_ids)}")
    print(f"Repeticiones: {NUM_REQUESTS - len(unique_ids)}")
    print(f"Cache hit rate esperado: ~{(NUM_REQUESTS - len(unique_ids)) / NUM_REQUESTS * 100:.1f}%")
    
    # Procesar requests
    results = []
    cache_hits = 0
    llm_calls = 0
    
    print("Enviando requests secuencialmente para evitar rate limiting...")
    print(f"INICIANDO EXPERIMENTO OLLAMA - {NUM_REQUESTS:,} REQUESTS")
    
    for i, question in enumerate(selected_questions, 1):
        if i % 10 != 1:
            print(f"[{i:4d}/{NUM_REQUESTS}] Procesando ID: {question['id']}", end=" ")
        else:
            print(f"Request {i}/{NUM_REQUESTS} - ID: {question['id']}")
            print(f"Pregunta: {question['question'][:80]}...")
        
        if i > 1:
            base_delay = 0.1
            if i % 10 == 1:
                print(f"Delay: {base_delay}s para evitar sobrecarga...")
            time.sleep(base_delay)
        
        start_time = time.time()
        result = send_request(question)
        end_time = time.time()
        
        if result:
            response_time = end_time - start_time
            results.append(result)
            
            source = result['source']
            score = result['score']
            wait_time = result.get('wait_time', 0)
            
            if source == 'cache':
                cache_hits += 1
                if i % 10 != 1:
                    print(f"CACHE ({response_time:.1f}s, score: {score:.3f})")
                else:
                    print(f"  Cache hit ({response_time:.1f}s) - Score: {score:.3f}")
                    
            elif source == 'database':
                cache_hits += 1  # Database también cuenta como hit
                if i % 10 != 1:
                    print(f"DB ({response_time:.1f}s, score: {score:.3f})")
                else:
                    print(f"  Database hit ({response_time:.1f}s) - Score: {score:.3f}")
                    
            elif source == 'async_processed':
                llm_calls += 1
                if i % 10 != 1:
                    print(f"ASYNC ({response_time:.1f}s, wait: {wait_time}s, score: {score:.3f})")
                else:
                    print(f"  Procesamiento asíncrono ({response_time:.1f}s, esperó: {wait_time}s)")
                    print(f"  Score: {score:.3f}, Intentos: {result.get('processing_attempts', 1)}")
                    answer_text = result.get('llm_answer', 'N/A')
                    if isinstance(answer_text, str) and len(answer_text) > 100:
                        print(f"  Respuesta: {answer_text[:100]}...")
                    else:
                        print(f"  Respuesta: {answer_text}")
            
            # Mostrar progreso cada 10 requests (más frecuente)
            if i % 10 == 0:
                rate = cache_hits / len(results) * 100 if results else 0
                avg_score = sum(r['score'] for r in results) / len(results) if results else 0
                progress_percent = (i / NUM_REQUESTS) * 100
                estimated_remaining = ((end_time - start_time) * (NUM_REQUESTS - i)) / 60  # en minutos
                
                print(f"PROGRESO: {i}/{NUM_REQUESTS} ({progress_percent:.1f}%)")
                print(f"Exitosas: {len(results)} | Cache hits: {cache_hits} | LLM calls: {llm_calls}")
                print(f"Cache hit rate: {rate:.1f}% | Score promedio: {avg_score:.3f}")
                print(f"Tiempo estimado restante: {estimated_remaining:.1f} minutos")
                print()
        else:
            print(f"  ERROR: Request falló definitivamente después de todos los reintentos")
            print()
            print(f"  Esperando 30 segundos antes de continuar...")
            time.sleep(30)
    
    # Guardar resultados
    print(f"Guardando {len(results)} resultados en {OUTPUT_FILE}...")
    
    summary = {
        'total_requests': NUM_REQUESTS,
        'successful_requests': len(results),
        'cache_hits': cache_hits,
        'llm_calls': llm_calls,
        'cache_hit_rate': cache_hits / len(results) if results else 0,
        'unique_questions': len(unique_ids),
        'timestamp': time.time()
    }
    
    output_data = {
        'summary': summary,
        'responses': results
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    # Mostrar estadísticas finales
    print("EXPERIMENTO OLLAMA COMPLETADO")
    
    if results:
        avg_score = sum(r['score'] for r in results) / len(results)
        max_score = max(r['score'] for r in results)
        min_score = min(r['score'] for r in results)
        
        print(f"ESTADÍSTICAS FINALES:")
        print(f"  • Total requests: {NUM_REQUESTS:,}")
        print(f"  • Requests exitosas: {len(results):,} ({len(results)/NUM_REQUESTS*100:.1f}%)")
        print(f"  • Cache hits: {cache_hits:,} ({cache_hits/len(results)*100:.1f}%)")
        print(f"  • LLM calls: {llm_calls:,} ({llm_calls/len(results)*100:.1f}%)")
        print()
        print(f"SCORES:")
        print(f"  • Score promedio: {avg_score:.4f}")
        print(f"  • Score máximo: {max_score:.4f}")
        print(f"  • Score mínimo: {min_score:.4f}")
        print(f"Resultados guardados en: {OUTPUT_FILE}")
    else:
        print("ERROR: No se procesaron requests exitosas")

if __name__ == "__main__":
    main()
