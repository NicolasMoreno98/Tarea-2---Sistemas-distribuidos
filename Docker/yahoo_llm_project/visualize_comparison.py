#!/usr/bin/env python3
"""
Visualización de Resultados: Comparación LRU vs LFU
Genera gráficas detalladas de performance y métricas
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# Configurar matplotlib para mejor visualización
plt.rcParams['figure.figsize'] = (14, 10)
plt.rcParams['font.size'] = 10
plt.style.use('seaborn-v0_8')

def load_data():
    """Cargar datos del experimento"""
    try:
        with open('lru_vs_lfu_comparison_20251001_203724.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Archivo de datos no encontrado")
        return None

def create_performance_charts(data):
    """Crear gráficas de comparación de performance"""
    
    lru_data = data['lru_experiment']
    lfu_data = data['lfu_experiment']
    
    # Crear figura con subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('🧪 COMPARACIÓN LRU vs LFU - Análisis de Performance', fontsize=16, fontweight='bold')
    
    # 1. Tiempo de Ejecución
    policies = ['LRU', 'LFU']
    durations = [lru_data['duration'], lfu_data['duration']]
    colors = ['#2E86AB', '#A23B72']
    
    bars1 = ax1.bar(policies, durations, color=colors, alpha=0.8, edgecolor='black')
    ax1.set_title('⏱️ Tiempo de Ejecución (segundos)', fontweight='bold')
    ax1.set_ylabel('Segundos')
    
    # Añadir valores en las barras
    for bar, duration in zip(bars1, durations):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                f'{duration:.2f}s', ha='center', fontweight='bold')
    
    # Diferencia porcentual
    diff_percent = ((lfu_data['duration'] - lru_data['duration']) / lru_data['duration']) * 100
    ax1.text(0.5, max(durations) * 0.8, f'LRU es {diff_percent:.1f}% más rápido', 
             ha='center', transform=ax1.transAxes, bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7))
    
    # 2. Cache Hit Rate
    cache_rates = [lru_data['cache_hit_rate'], lfu_data['cache_hit_rate']]
    bars2 = ax2.bar(policies, cache_rates, color=colors, alpha=0.8, edgecolor='black')
    ax2.set_title('📈 Cache Hit Rate (%)', fontweight='bold')
    ax2.set_ylabel('Porcentaje (%)')
    ax2.set_ylim(0, 100)
    
    for bar, rate in zip(bars2, cache_rates):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                f'{rate:.1f}%', ha='center', fontweight='bold')
    
    # 3. Scores Promedio
    avg_scores = [lru_data['avg_score'], lfu_data['avg_score']]
    bars3 = ax3.bar(policies, avg_scores, color=colors, alpha=0.8, edgecolor='black')
    ax3.set_title('⭐ Score Promedio BERTScore', fontweight='bold')
    ax3.set_ylabel('Score')
    ax3.set_ylim(0.85, 0.89)
    
    for bar, score in zip(bars3, avg_scores):
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001, 
                f'{score:.4f}', ha='center', fontweight='bold')
    
    # 4. Distribución Cache vs LLM
    categories = ['Cache Hits', 'LLM Calls']
    lru_values = [lru_data['cache_hits'], lru_data['llm_calls']]
    lfu_values = [lfu_data['cache_hits'], lfu_data['llm_calls']]
    
    x = np.arange(len(categories))
    width = 0.35
    
    bars4_lru = ax4.bar(x - width/2, lru_values, width, label='LRU', color=colors[0], alpha=0.8)
    bars4_lfu = ax4.bar(x + width/2, lfu_values, width, label='LFU', color=colors[1], alpha=0.8)
    
    ax4.set_title('🔄 Distribución de Requests', fontweight='bold')
    ax4.set_ylabel('Número de Requests')
    ax4.set_xticks(x)
    ax4.set_xticklabels(categories)
    ax4.legend()
    
    # Añadir valores en las barras
    for bars in [bars4_lru, bars4_lfu]:
        for bar in bars:
            ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, 
                    f'{int(bar.get_height())}', ha='center', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('lru_vs_lfu_performance_comparison.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    return fig

def create_timeline_chart(data):
    """Crear gráfica de timeline de respuestas"""
    
    lru_results = data['lru_experiment']['results']
    lfu_results = data['lfu_experiment']['results']
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10))
    fig.suptitle('📊 Timeline de Respuestas: LRU vs LFU', fontsize=16, fontweight='bold')
    
    # Separar cache hits y LLM calls para LRU
    lru_cache_times = [r['response_time'] for r in lru_results if r['source'] == 'cache']
    lru_llm_times = [r['response_time'] for r in lru_results if r['source'] == 'llm']
    lru_cache_indices = [i for i, r in enumerate(lru_results) if r['source'] == 'cache']
    lru_llm_indices = [i for i, r in enumerate(lru_results) if r['source'] == 'llm']
    
    # Gráfica LRU
    ax1.scatter(lru_cache_indices, lru_cache_times, c='green', alpha=0.6, s=30, label='Cache Hits')
    ax1.scatter(lru_llm_indices, lru_llm_times, c='red', alpha=0.8, s=50, label='LLM Calls')
    ax1.set_title('🔵 LRU - Timeline de Respuestas', fontweight='bold')
    ax1.set_ylabel('Tiempo (segundos)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Separar cache hits y LLM calls para LFU
    lfu_cache_times = [r['response_time'] for r in lfu_results if r['source'] == 'cache']
    lfu_llm_times = [r['response_time'] for r in lfu_results if r['source'] == 'llm']
    lfu_cache_indices = [i for i, r in enumerate(lfu_results) if r['source'] == 'cache']
    lfu_llm_indices = [i for i, r in enumerate(lfu_results) if r['source'] == 'llm']
    
    # Gráfica LFU
    ax2.scatter(lfu_cache_indices, lfu_cache_times, c='green', alpha=0.6, s=30, label='Cache Hits')
    ax2.scatter(lfu_llm_indices, lfu_llm_times, c='red', alpha=0.8, s=50, label='LLM Calls')
    ax2.set_title('🔴 LFU - Timeline de Respuestas', fontweight='bold')
    ax2.set_xlabel('Número de Request')
    ax2.set_ylabel('Tiempo (segundos)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('lru_vs_lfu_timeline.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    return fig

def create_detailed_metrics_chart(data):
    """Crear gráfica detallada de métricas"""
    
    lru_data = data['lru_experiment']
    lfu_data = data['lfu_experiment']
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('📈 Análisis Detallado de Métricas', fontsize=16, fontweight='bold')
    
    # 1. Eficiencia Temporal (Requests por segundo)
    lru_rps = lru_data['successful_requests'] / lru_data['duration']
    lfu_rps = lfu_data['successful_requests'] / lfu_data['duration']
    
    policies = ['LRU', 'LFU']
    rps_values = [lru_rps, lfu_rps]
    colors = ['#2E86AB', '#A23B72']
    
    bars1 = ax1.bar(policies, rps_values, color=colors, alpha=0.8, edgecolor='black')
    ax1.set_title('🚀 Throughput (Requests/segundo)', fontweight='bold')
    ax1.set_ylabel('Requests por segundo')
    
    for bar, rps in zip(bars1, rps_values):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, 
                f'{rps:.2f}', ha='center', fontweight='bold')
    
    # 2. Distribución de Scores
    lru_scores = [r['score'] for r in lru_data['results']]
    lfu_scores = [r['score'] for r in lfu_data['results']]
    
    ax2.hist(lru_scores, bins=15, alpha=0.7, label='LRU', color=colors[0], density=True)
    ax2.hist(lfu_scores, bins=15, alpha=0.7, label='LFU', color=colors[1], density=True)
    ax2.set_title('📊 Distribución de Scores BERTScore', fontweight='bold')
    ax2.set_xlabel('Score')
    ax2.set_ylabel('Densidad')
    ax2.legend()
    
    # 3. Tiempo promedio por tipo de request
    lru_cache_avg = np.mean([r['response_time'] for r in lru_data['results'] if r['source'] == 'cache'])
    lru_llm_avg = np.mean([r['response_time'] for r in lru_data['results'] if r['source'] == 'llm'])
    lfu_cache_avg = np.mean([r['response_time'] for r in lfu_data['results'] if r['source'] == 'cache'])
    lfu_llm_avg = np.mean([r['response_time'] for r in lfu_data['results'] if r['source'] == 'llm'])
    
    x = np.arange(2)
    width = 0.35
    
    ax3.bar(x - width/2, [lru_cache_avg, lru_llm_avg], width, label='LRU', color=colors[0], alpha=0.8)
    ax3.bar(x + width/2, [lfu_cache_avg, lfu_llm_avg], width, label='LFU', color=colors[1], alpha=0.8)
    ax3.set_title('⏱️ Tiempo Promedio por Tipo', fontweight='bold')
    ax3.set_ylabel('Tiempo (segundos)')
    ax3.set_xticks(x)
    ax3.set_xticklabels(['Cache Hits', 'LLM Calls'])
    ax3.legend()
    
    # 4. Resumen de Ventajas
    metrics = ['Velocidad\\n(menor tiempo)', 'Cache Rate\\n(% hits)', 'Calidad\\n(score)', 'Throughput\\n(req/s)']
    lru_wins = [1, 0, 0, 1]  # LRU gana en velocidad y throughput
    lfu_wins = [0, 0, 1, 0]  # LFU gana en calidad
    ties = [0, 1, 0, 0]      # Empate en cache rate
    
    x = np.arange(len(metrics))
    width = 0.25
    
    ax4.bar(x - width, lru_wins, width, label='LRU Mejor', color=colors[0], alpha=0.8)
    ax4.bar(x, lfu_wins, width, label='LFU Mejor', color=colors[1], alpha=0.8)
    ax4.bar(x + width, ties, width, label='Empate', color='gray', alpha=0.8)
    
    ax4.set_title('🏆 Resumen de Ventajas', fontweight='bold')
    ax4.set_ylabel('Ganador (1 = Sí, 0 = No)')
    ax4.set_xticks(x)
    ax4.set_xticklabels(metrics)
    ax4.legend()
    ax4.set_ylim(0, 1.2)
    
    plt.tight_layout()
    plt.savefig('lru_vs_lfu_detailed_metrics.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    return fig

def generate_summary_report(data):
    """Generar reporte resumen textual"""
    
    lru_data = data['lru_experiment']
    lfu_data = data['lfu_experiment']
    
    print("\\n" + "="*80)
    print("📋 REPORTE FINAL DE COMPARACIÓN LRU vs LFU")
    print("="*80)
    
    print(f"\\n🕐 DATOS DEL EXPERIMENTO:")
    print(f"   • Fecha: {data['timestamp']}")
    print(f"   • Total requests por política: 100")
    print(f"   • TTL configurado: 1 hora")
    print(f"   • Límite memoria Redis: 2MB")
    
    print(f"\\n⚡ PERFORMANCE:")
    print(f"   • LRU Duration: {lru_data['duration']:.2f}s")
    print(f"   • LFU Duration: {lfu_data['duration']:.2f}s")
    print(f"   • Diferencia: {abs(lru_data['duration'] - lfu_data['duration']):.2f}s")
    
    winner = "LRU" if lru_data['duration'] < lfu_data['duration'] else "LFU"
    improvement = abs(lru_data['duration'] - lfu_data['duration']) / max(lru_data['duration'], lfu_data['duration']) * 100
    print(f"   • 🏆 Más rápido: {winner} ({improvement:.1f}% mejor)")
    
    print(f"\\n📊 CACHE EFFICIENCY:")
    print(f"   • LRU Cache Hits: {lru_data['cache_hits']}/100 ({lru_data['cache_hit_rate']:.1f}%)")
    print(f"   • LFU Cache Hits: {lfu_data['cache_hits']}/100 ({lfu_data['cache_hit_rate']:.1f}%)")
    
    print(f"\\n⭐ CALIDAD DE RESPUESTAS:")
    print(f"   • LRU Score Promedio: {lru_data['avg_score']:.4f}")
    print(f"   • LFU Score Promedio: {lfu_data['avg_score']:.4f}")
    
    quality_winner = "LFU" if lfu_data['avg_score'] > lru_data['avg_score'] else "LRU"
    quality_diff = abs(lfu_data['avg_score'] - lru_data['avg_score'])
    print(f"   • 🏆 Mejor calidad: {quality_winner} (+{quality_diff:.4f})")
    
    print(f"\\n🎯 RECOMENDACIÓN FINAL:")
    if winner == "LRU":
        print("   ✅ LRU es la mejor opción para este workload")
        print("   📈 Ventajas: Mayor velocidad, mejor throughput")
        print("   📉 Desventajas: Score ligeramente inferior")
    else:
        print("   ✅ LFU es la mejor opción para este workload")
        print("   📈 Ventajas: Mejor calidad de respuestas")
        print("   📉 Desventajas: Menor velocidad")
    
    print("="*80)

def main():
    """Función principal"""
    print("🎨 GENERANDO VISUALIZACIONES LRU vs LFU...")
    print("="*60)
    
    # Cargar datos
    data = load_data()
    if not data:
        return
    
    # Generar gráficas
    print("📊 Creando gráficas de performance...")
    create_performance_charts(data)
    
    print("📈 Creando timeline de respuestas...")
    create_timeline_chart(data)
    
    print("📋 Creando métricas detalladas...")
    create_detailed_metrics_chart(data)
    
    # Generar reporte textual
    generate_summary_report(data)
    
    print("\\n✅ ¡Visualizaciones completadas!")
    print("📁 Archivos generados:")
    print("   • lru_vs_lfu_performance_comparison.png")
    print("   • lru_vs_lfu_timeline.png")
    print("   • lru_vs_lfu_detailed_metrics.png")

if __name__ == "__main__":
    main()