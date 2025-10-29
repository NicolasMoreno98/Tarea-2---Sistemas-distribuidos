#!/usr/bin/env python3
"""
Generador de experimentos comparativos LRU vs LFU
Versión simplificada para ejecutar localmente
"""

import requests
import json
import time
import subprocess
from datetime import datetime

API_URL = "http://localhost:5000/process"

# Dataset de prueba para los experimentos
sample_questions = [
    {"id": "1", "question": "What is artificial intelligence?", "best_answer": "AI is the simulation of human intelligence processes by machines"},
    {"id": "2", "question": "How does machine learning work?", "best_answer": "Machine learning uses algorithms to find patterns in data"},
    {"id": "3", "question": "What is Python programming?", "best_answer": "Python is a high-level programming language"},
    {"id": "4", "question": "How do databases work?", "best_answer": "Databases store and organize data for efficient retrieval"},
    {"id": "5", "question": "What is cloud computing?", "best_answer": "Cloud computing delivers computing services over the internet"},
    {"id": "1", "question": "What is artificial intelligence?", "best_answer": "AI is the simulation of human intelligence processes by machines"},  # Repetida para cache hit
    {"id": "6", "question": "What is cybersecurity?", "best_answer": "Cybersecurity protects digital information from threats"},
    {"id": "2", "question": "How does machine learning work?", "best_answer": "Machine learning uses algorithms to find patterns in data"},  # Repetida
    {"id": "7", "question": "What is data science?", "best_answer": "Data science extracts insights from structured and unstructured data"},
    {"id": "3", "question": "What is Python programming?", "best_answer": "Python is a high-level programming language"},  # Repetida
] * 10  # 100 requests total con repeticiones para cache hits

def change_redis_policy(policy):
    """Cambiar política Redis"""
    print(f"\n🔧 Cambiando Redis a política: {policy}")
    
    # Cambiar configuración
    cmd = f'docker exec yahoo_llm_project-redis-1 redis-cli CONFIG SET maxmemory-policy {policy}'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        # Verificar cambio
        cmd_verify = 'docker exec yahoo_llm_project-redis-1 redis-cli CONFIG GET maxmemory-policy'
        verify = subprocess.run(cmd_verify, shell=True, capture_output=True, text=True)
        
        if policy in verify.stdout:
            print(f"✅ Redis configurado exitosamente: {policy}")
            return True
    
    print(f"❌ Error configurando Redis: {policy}")
    return False

def clear_cache():
    """Limpiar cache Redis"""
    cmd = 'docker exec yahoo_llm_project-redis-1 redis-cli FLUSHALL'
    subprocess.run(cmd, shell=True)
    print("🧹 Cache Redis limpiado")

def run_experiment(policy_name, num_requests=100):
    """Ejecutar experimento con política específica"""
    print(f"\n🚀 EXPERIMENTO {policy_name.upper()} - {num_requests} REQUESTS")
    print("="*60)
    
    results = []
    cache_hits = 0
    llm_calls = 0
    total_score = 0
    successful_requests = 0
    
    start_time = time.time()
    
    for i, question_data in enumerate(sample_questions[:num_requests], 1):
        print(f"\r[{i:3d}/{num_requests}] Procesando ID: {question_data['id']}", end="", flush=True)
        
        try:
            response = requests.post(API_URL, json=question_data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                
                # Determinar si fue cache hit o LLM call
                if result.get('source') == 'cache':
                    cache_hits += 1
                    print(" [CACHE]", end="")
                else:
                    llm_calls += 1
                    print(" [LLM]", end="")
                
                successful_requests += 1
                score = result.get('score', 0)
                total_score += score
                
                results.append({
                    'question_id': question_data['id'],
                    'source': result.get('source', 'unknown'),
                    'score': score,
                    'response_time': time.time() - start_time
                })
                
        except Exception as e:
            print(f" [ERROR: {str(e)[:30]}]", end="")
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Calcular métricas
    avg_score = total_score / successful_requests if successful_requests > 0 else 0
    cache_hit_rate = (cache_hits / successful_requests * 100) if successful_requests > 0 else 0
    
    print(f"\n\n📊 RESULTADOS {policy_name.upper()}:")
    print(f"   • Duración: {duration:.2f} segundos")
    print(f"   • Requests exitosas: {successful_requests}/{num_requests} ({successful_requests/num_requests*100:.1f}%)")
    print(f"   • Cache hits: {cache_hits} ({cache_hit_rate:.1f}%)")
    print(f"   • LLM calls: {llm_calls}")
    print(f"   • Score promedio: {avg_score:.4f}")
    
    return {
        'policy': policy_name,
        'duration': duration,
        'successful_requests': successful_requests,
        'cache_hits': cache_hits,
        'llm_calls': llm_calls,
        'cache_hit_rate': cache_hit_rate,
        'avg_score': avg_score,
        'results': results
    }

def compare_results(lru_result, lfu_result):
    """Comparar resultados de ambos experimentos"""
    print("\n" + "="*80)
    print("📊 COMPARACIÓN LRU vs LFU")
    print("="*80)
    
    print(f"\n⏱️  TIEMPO DE EJECUCIÓN:")
    print(f"   LRU: {lru_result['duration']:.2f}s")
    print(f"   LFU: {lfu_result['duration']:.2f}s")
    
    if lru_result['duration'] < lfu_result['duration']:
        diff = lfu_result['duration'] - lru_result['duration']
        print(f"   🏆 LRU fue {diff:.2f}s más rápido")
    else:
        diff = lru_result['duration'] - lfu_result['duration']
        print(f"   🏆 LFU fue {diff:.2f}s más rápido")
    
    print(f"\n📈 CACHE PERFORMANCE:")
    print(f"   LRU Cache Hit Rate: {lru_result['cache_hit_rate']:.1f}%")
    print(f"   LFU Cache Hit Rate: {lfu_result['cache_hit_rate']:.1f}%")
    
    print(f"\n⭐ CALIDAD DE RESPUESTAS:")
    print(f"   LRU Score Promedio: {lru_result['avg_score']:.4f}")
    print(f"   LFU Score Promedio: {lfu_result['avg_score']:.4f}")
    
    # Guardar reporte comparativo
    comparison = {
        'timestamp': datetime.now().isoformat(),
        'lru_experiment': lru_result,
        'lfu_experiment': lfu_result,
        'summary': {
            'faster_policy': 'LRU' if lru_result['duration'] < lfu_result['duration'] else 'LFU',
            'better_cache_rate': 'LRU' if lru_result['cache_hit_rate'] > lfu_result['cache_hit_rate'] else 'LFU',
            'better_score': 'LRU' if lru_result['avg_score'] > lfu_result['avg_score'] else 'LFU'
        }
    }
    
    filename = f"lru_vs_lfu_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(comparison, f, indent=2)
    
    print(f"\n💾 Reporte guardado en: {filename}")
    return comparison

def main():
    """Ejecutar experimento comparativo completo"""
    print("🧪 EXPERIMENTO COMPARATIVO LRU vs LFU")
    print("="*50)
    
    # EXPERIMENTO 1: LRU
    if not change_redis_policy("allkeys-lru"):
        return
    
    clear_cache()
    lru_result = run_experiment("LRU", 100)
    
    # Pausa entre experimentos
    print("\n⏸️  Pausa de 15 segundos...")
    time.sleep(15)
    
    # EXPERIMENTO 2: LFU
    if not change_redis_policy("allkeys-lfu"):
        return
    
    clear_cache()
    lfu_result = run_experiment("LFU", 100)
    
    # Comparar resultados
    compare_results(lru_result, lfu_result)
    
    # Restaurar LRU
    change_redis_policy("allkeys-lru")
    
    print("\n🎉 ¡EXPERIMENTO COMPLETADO!")

if __name__ == "__main__":
    main()