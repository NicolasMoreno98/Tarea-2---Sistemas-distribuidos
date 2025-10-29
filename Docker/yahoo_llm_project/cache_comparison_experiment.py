#!/usr/bin/env python3
"""
Experimento Comparativo: LRU vs LFU Cache Policies
Ejecuta 100 pruebas con cada política y compara resultados
"""

import subprocess
import json
import time
import os
from datetime import datetime

def run_docker_command(command):
    """Ejecutar comando Docker y devolver resultado"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def change_redis_policy(policy="allkeys-lru"):
    """Cambiar política de Redis (lru o lfu)"""
    print(f"\n🔧 Cambiando política Redis a: {policy}")
    
    # Cambiar configuración en redis.conf
    redis_config = f"""# Redis LRU/LFU Comparison Configuration
maxmemory 2mb
maxmemory-policy {policy}
save ""
appendonly no
"""
    
    with open("redis/redis.conf", "w") as f:
        f.write(redis_config)
    
    # Reiniciar Redis para aplicar cambios
    print("🔄 Reiniciando Redis...")
    run_docker_command("docker-compose restart redis")
    time.sleep(10)  # Esperar que Redis se reinicie
    
    # Verificar que el cambio se aplicó
    success, output, _ = run_docker_command(
        "docker exec yahoo_llm_project-redis-1 redis-cli CONFIG GET maxmemory-policy"
    )
    
    if success and policy in output:
        print(f"✅ Política Redis cambiada exitosamente a: {policy}")
        return True
    else:
        print(f"❌ Error cambiando política Redis")
        return False

def clear_redis_cache():
    """Limpiar cache de Redis"""
    print("🧹 Limpiando cache Redis...")
    run_docker_command("docker exec yahoo_llm_project-redis-1 redis-cli FLUSHALL")

def run_experiment(policy_name, num_requests=100):
    """Ejecutar un experimento con una política específica"""
    print(f"\n🚀 INICIANDO EXPERIMENTO {policy_name.upper()}")
    print("="*60)
    
    # Timestamp para archivos únicos
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"/data/experiment_{policy_name}_{timestamp}.json"
    
    # Limpiar cache antes del experimento
    clear_redis_cache()
    
    # Modificar OUTPUT_FILE en el contenedor para este experimento
    run_docker_command(f"""docker exec yahoo_llm_project-traffic-generator-1 sed -i 's|OUTPUT_FILE = "/data/response.json"|OUTPUT_FILE = "{output_file}"|' generator.py""")
    
    # Ejecutar el generador de tráfico
    print(f"📊 Ejecutando {num_requests} requests con política {policy_name}...")
    start_time = time.time()
    
    success, output, error = run_docker_command(
        "docker exec yahoo_llm_project-traffic-generator-1 python generator.py"
    )
    
    end_time = time.time()
    experiment_duration = end_time - start_time
    
    if success:
        print(f"✅ Experimento {policy_name} completado en {experiment_duration:.2f} segundos")
        
        # Obtener estadísticas de Redis
        _, redis_info, _ = run_docker_command(
            "docker exec yahoo_llm_project-redis-1 redis-cli INFO memory"
        )
        
        return {
            "policy": policy_name,
            "timestamp": timestamp,
            "duration": experiment_duration,
            "output_file": output_file,
            "success": True,
            "redis_memory_info": redis_info,
            "generator_output": output[-2000:]  # Últimas 2000 chars
        }
    else:
        print(f"❌ Error en experimento {policy_name}: {error}")
        return {
            "policy": policy_name,
            "timestamp": timestamp,
            "success": False,
            "error": error
        }

def analyze_results(lru_result, lfu_result):
    """Analizar y comparar resultados de ambos experimentos"""
    print("\n" + "="*80)
    print("📊 ANÁLISIS COMPARATIVO DE RESULTADOS")
    print("="*80)
    
    # Extraer métricas de los outputs
    lru_metrics = extract_metrics_from_output(lru_result.get("generator_output", ""))
    lfu_metrics = extract_metrics_from_output(lfu_result.get("generator_output", ""))
    
    # Comparación de duración
    print(f"\n⏱️  TIEMPO DE EJECUCIÓN:")
    print(f"   LRU: {lru_result.get('duration', 0):.2f} segundos")
    print(f"   LFU: {lfu_result.get('duration', 0):.2f} segundos")
    
    if lru_result.get('duration', 0) and lfu_result.get('duration', 0):
        diff = abs(lru_result['duration'] - lfu_result['duration'])
        faster = "LRU" if lru_result['duration'] < lfu_result['duration'] else "LFU"
        print(f"   🏆 {faster} fue {diff:.2f}s más rápido")
    
    # Comparación de métricas
    print(f"\n📈 MÉTRICAS COMPARATIVAS:")
    if lru_metrics and lfu_metrics:
        print(f"   Cache Hit Rate:")
        print(f"     LRU: {lru_metrics.get('cache_hit_rate', 'N/A')}")
        print(f"     LFU: {lfu_metrics.get('cache_hit_rate', 'N/A')}")
        
        print(f"   Score Promedio:")
        print(f"     LRU: {lru_metrics.get('avg_score', 'N/A')}")
        print(f"     LFU: {lfu_metrics.get('avg_score', 'N/A')}")
        
        print(f"   Requests Exitosas:")
        print(f"     LRU: {lru_metrics.get('successful_requests', 'N/A')}")
        print(f"     LFU: {lfu_metrics.get('successful_requests', 'N/A')}")
    
    # Crear reporte final
    comparison_report = {
        "timestamp": datetime.now().isoformat(),
        "lru_experiment": lru_result,
        "lfu_experiment": lfu_result,
        "lru_metrics": lru_metrics,
        "lfu_metrics": lfu_metrics,
        "comparison_summary": {
            "faster_policy": faster if 'faster' in locals() else "Unknown",
            "time_difference": diff if 'diff' in locals() else 0
        }
    }
    
    # Guardar reporte
    report_filename = f"cache_comparison_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_filename, 'w') as f:
        json.dump(comparison_report, f, indent=2)
    
    print(f"\n💾 Reporte completo guardado en: {report_filename}")
    return comparison_report

def extract_metrics_from_output(output):
    """Extraer métricas del output del generador"""
    try:
        metrics = {}
        lines = output.split('\n')
        
        for line in lines:
            if "Cache hit rate:" in line:
                rate = line.split(":")[-1].strip()
                metrics['cache_hit_rate'] = rate
            elif "Score promedio:" in line:
                score = line.split(":")[-1].strip()
                metrics['avg_score'] = score
            elif "Requests exitosas:" in line:
                requests = line.split(":")[1].strip().split()[0]
                metrics['successful_requests'] = requests
                
        return metrics
    except Exception as e:
        print(f"⚠️ Error extrayendo métricas: {e}")
        return {}

def main():
    """Función principal del experimento comparativo"""
    print("🧪 EXPERIMENTO COMPARATIVO: LRU vs LFU CACHE POLICIES")
    print("="*80)
    print("📋 Configuración:")
    print("   • Número de requests: 100 por experimento")
    print("   • Políticas a comparar: LRU vs LFU")
    print("   • TTL: 1 hora para ambas")
    print("   • Memoria límite: 2MB")
    print("="*80)
    
    # Experimento 1: LRU (ya configurado)
    print("\n🔵 FASE 1: EXPERIMENTO CON LRU")
    if not change_redis_policy("allkeys-lru"):
        print("❌ Error configurando LRU, abortando experimento")
        return
    
    lru_result = run_experiment("lru", 100)
    
    # Pausa entre experimentos
    print("\n⏸️  Pausa de 30 segundos entre experimentos...")
    time.sleep(30)
    
    # Experimento 2: LFU
    print("\n🔴 FASE 2: EXPERIMENTO CON LFU")
    if not change_redis_policy("allkeys-lfu"):
        print("❌ Error configurando LFU, abortando experimento")
        return
        
    lfu_result = run_experiment("lfu", 100)
    
    # Análisis comparativo
    analyze_results(lru_result, lfu_result)
    
    # Restaurar configuración original (LRU)
    print(f"\n🔄 Restaurando configuración original (LRU)...")
    change_redis_policy("allkeys-lru")
    
    print("\n🎉 ¡EXPERIMENTO COMPARATIVO COMPLETADO!")
    print("="*80)

if __name__ == "__main__":
    # Cambiar al directorio correcto
    os.chdir("D:/U/Sistemas Distribuidos/Docker/yahoo_llm_project")
    main()