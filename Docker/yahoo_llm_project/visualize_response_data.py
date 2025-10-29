#!/usr/bin/env python3
"""
Script para visualizar los datos del archivo response.json
Genera gráficos de pie chart, nube de puntos para tiempo y scores
"""

import json
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from collections import Counter
import pandas as pd
from datetime import datetime

# Configurar el estilo
plt.style.use('default')
sns.set_palette("husl")
plt.rcParams['figure.figsize'] = (15, 12)

def load_data(file_path):
    """Cargar y procesar los datos del JSON"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data

def extract_metrics(data):
    """Extraer métricas de los datos"""
    summary = data.get('summary', {})
    responses = data.get('responses', [])
    
    # Métricas del resumen
    total_requests = summary.get('total_requests', 0)
    successful_requests = summary.get('successful_requests', 0)
    cache_hits = summary.get('cache_hits', 0)
    unique_questions = summary.get('unique_questions', 0)
    cache_hit_rate = summary.get('cache_hit_rate', 0)
    
    # Extraer datos de respuestas individuales
    question_ids = []
    scores = []
    timestamps = []
    sources = []
    
    for response in responses:
        question_ids.append(response.get('question_id', ''))
        scores.append(response.get('score', 0.0))
        timestamps.append(response.get('timestamp', 0))
        sources.append(response.get('source', 'unknown'))
    
    # Calcular tiempos relativos (diferencia desde el primer timestamp)
    if timestamps:
        min_timestamp = min(timestamps)
        relative_times = [(t - min_timestamp) / 60 for t in timestamps]  # en minutos
    else:
        relative_times = []
    
    # Contar preguntas repetidas
    question_counts = Counter(question_ids)
    repeated_questions = sum(1 for count in question_counts.values() if count > 1)
    
    return {
        'total_requests': total_requests,
        'successful_requests': successful_requests,
        'cache_hits': cache_hits,
        'unique_questions': unique_questions,
        'repeated_questions': repeated_questions,
        'cache_hit_rate': cache_hit_rate,
        'scores': scores,
        'relative_times': relative_times,
        'sources': sources,
        'question_counts': question_counts
    }

def create_visualizations(metrics):
    """Crear las visualizaciones solicitadas"""
    
    # Crear figura con subplots
    fig = plt.figure(figsize=(20, 15))
    
    # 1. PIE CHART - Comparación de requests totales
    ax1 = plt.subplot(2, 3, 1)
    
    # Calcular valores para el pie chart
    unique_qs = metrics['unique_questions']
    total_requests = metrics['total_requests']
    cache_hits = metrics['cache_hits']
    
    # Preguntas nuevas vs repetidas vs cache hits
    new_questions = unique_qs
    repeated_requests = total_requests - unique_qs - cache_hits
    
    labels = ['Preguntas Únicas', 'Preguntas Repetidas', 'Cache Hits']
    sizes = [new_questions, repeated_requests, cache_hits]
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
    explode = (0.05, 0.05, 0.1)  # explode el slice de cache hits
    
    wedges, texts, autotexts = ax1.pie(sizes, explode=explode, labels=labels, 
                                       colors=colors, autopct='%1.1f%%', 
                                       shadow=True, startangle=90)
    
    ax1.set_title('Distribución de Requests Totales\n' + 
                  f'Total: {metrics["total_requests"]:,} requests', 
                  fontsize=14, fontweight='bold', pad=20)
    
    # Mejorar apariencia
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(10)
    
    # 2. NUBE DE PUNTOS - Tiempo de respuesta
    ax2 = plt.subplot(2, 3, 2)
    
    x_times = range(len(metrics['relative_times']))
    scatter1 = ax2.scatter(x_times, metrics['relative_times'], 
                          alpha=0.6, c=metrics['relative_times'], 
                          cmap='viridis', s=50)
    
    ax2.set_title('Distribución Temporal de Requests', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Número de Request')
    ax2.set_ylabel('Tiempo Relativo (minutos)')
    ax2.grid(True, alpha=0.3)
    
    # Línea de tendencia
    if len(metrics['relative_times']) > 1:
        z = np.polyfit(x_times, metrics['relative_times'], 1)
        p = np.poly1d(z)
        ax2.plot(x_times, p(x_times), "r--", alpha=0.8, label='Tendencia')
        ax2.legend()
    
    plt.colorbar(scatter1, ax=ax2, label='Tiempo (min)')
    
    # 3. NUBE DE PUNTOS - Scores
    ax3 = plt.subplot(2, 3, 3)
    
    x_scores = range(len(metrics['scores']))
    scatter2 = ax3.scatter(x_scores, metrics['scores'], 
                          alpha=0.6, c=metrics['scores'], 
                          cmap='RdYlBu', s=50)
    
    ax3.set_title('Distribución de BERTScores', fontsize=14, fontweight='bold')
    ax3.set_xlabel('Número de Request')
    ax3.set_ylabel('BERTScore')
    ax3.grid(True, alpha=0.3)
    
    # Línea de media
    if metrics['scores']:
        mean_score = np.mean(metrics['scores'])
        ax3.axhline(y=mean_score, color='red', linestyle='--', alpha=0.8,
                   label=f'Media: {mean_score:.3f}')
        ax3.legend()
    
    plt.colorbar(scatter2, ax=ax3, label='Score')
    
    # 4. HISTOGRAMA - Distribución de Scores
    ax4 = plt.subplot(2, 3, 4)
    
    ax4.hist(metrics['scores'], bins=30, alpha=0.7, color='skyblue', 
             edgecolor='black', density=True)
    ax4.set_title('Histograma de BERTScores', fontsize=14, fontweight='bold')
    ax4.set_xlabel('BERTScore')
    ax4.set_ylabel('Densidad')
    ax4.grid(True, alpha=0.3)
    
    # Agregar línea de media
    if metrics['scores']:
        mean_score = np.mean(metrics['scores'])
        ax4.axvline(x=mean_score, color='red', linestyle='--', 
                   label=f'Media: {mean_score:.3f}')
        ax4.legend()
    
    # 5. GRÁFICO DE BARRAS - Cache vs LLM calls
    ax5 = plt.subplot(2, 3, 5)
    
    sources = metrics['sources']
    source_counts = Counter(sources)
    
    categories = list(source_counts.keys())
    values = list(source_counts.values())
    colors_bar = ['#FF6B6B' if cat == 'cache' else '#4ECDC4' for cat in categories]
    
    bars = ax5.bar(categories, values, color=colors_bar, alpha=0.8)
    ax5.set_title('Fuente de Respuestas', fontsize=14, fontweight='bold')
    ax5.set_ylabel('Cantidad de Responses')
    ax5.grid(True, alpha=0.3, axis='y')
    
    # Agregar valores en las barras
    for bar, value in zip(bars, values):
        ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.01,
                f'{value:,}', ha='center', va='bottom', fontweight='bold')
    
    # 6. ESTADÍSTICAS TEXTUALES
    ax6 = plt.subplot(2, 3, 6)
    ax6.axis('off')
    
    # Calcular estadísticas adicionales
    if metrics['scores']:
        score_stats = {
            'media': np.mean(metrics['scores']),
            'mediana': np.median(metrics['scores']),
            'std': np.std(metrics['scores']),
            'min': np.min(metrics['scores']),
            'max': np.max(metrics['scores'])
        }
    else:
        score_stats = {'media': 0, 'mediana': 0, 'std': 0, 'min': 0, 'max': 0}
    
    if metrics['relative_times']:
        time_stats = {
            'duracion_total': max(metrics['relative_times']),
            'tiempo_promedio': np.mean(np.diff(metrics['relative_times'])) if len(metrics['relative_times']) > 1 else 0
        }
    else:
        time_stats = {'duracion_total': 0, 'tiempo_promedio': 0}
    
    stats_text = f"""
ESTADÍSTICAS DEL EXPERIMENTO

📊 REQUESTS:
  • Total: {metrics['total_requests']:,}
  • Exitosas: {metrics['successful_requests']:,}
  • Tasa éxito: {(metrics['successful_requests']/metrics['total_requests']*100):.1f}%

🔄 CACHE:
  • Cache hits: {metrics['cache_hits']:,}
  • Hit rate: {metrics['cache_hit_rate']*100:.1f}%
  • LLM calls: {metrics['total_requests'] - metrics['cache_hits']:,}

❓ PREGUNTAS:
  • Únicas: {metrics['unique_questions']:,}
  • Repetidas: {metrics['repeated_questions']:,}

📈 BERTSCORE:
  • Media: {score_stats['media']:.3f}
  • Rango: {score_stats['min']:.3f} - {score_stats['max']:.3f}
  • Std: {score_stats['std']:.3f}

⏱️ TIEMPO:
  • Duración total: {time_stats['duracion_total']:.1f} min
  • Requests/min: {metrics['total_requests']/max(1, time_stats['duracion_total']):.1f}
    """
    
    ax6.text(0.05, 0.95, stats_text, transform=ax6.transAxes, fontsize=11,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
    
    # Ajustar layout
    plt.tight_layout()
    
    # Guardar el gráfico
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f'response_analysis_{timestamp}.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"✅ Gráfico guardado como: {filename}")
    
    return fig

def main():
    """Función principal"""
    print("🔍 Analizando datos del archivo response.json...")
    
    # Cargar datos
    try:
        data = load_data('response.json')
        print(f"✅ Datos cargados: {len(data.get('responses', []))} responses encontradas")
    except FileNotFoundError:
        print("❌ Error: No se encontró el archivo 'response.json'")
        print("   Asegúrate de que el archivo esté en el mismo directorio que este script")
        return
    except json.JSONDecodeError:
        print("❌ Error: El archivo response.json no es un JSON válido")
        return
    
    # Extraer métricas
    metrics = extract_metrics(data)
    
    # Crear visualizaciones
    print("📊 Generando visualizaciones...")
    fig = create_visualizations(metrics)
    
    # Mostrar gráfico
    plt.show()
    
    print(f"""
🎯 ANÁLISIS COMPLETADO

📋 Resumen de datos procesados:
  • Total requests: {metrics['total_requests']:,}
  • Cache hit rate: {metrics['cache_hit_rate']*100:.1f}%
  • Preguntas únicas: {metrics['unique_questions']:,}
  • Score promedio: {np.mean(metrics['scores']):.3f}
  
📈 Gráficos generados:
  1. Pie Chart - Distribución de requests
  2. Scatter Plot - Tiempo de respuesta
  3. Scatter Plot - BERTScores
  4. Histograma - Distribución de scores
  5. Bar Chart - Fuentes de respuesta
  6. Panel de estadísticas
    """)

if __name__ == "__main__":
    main()