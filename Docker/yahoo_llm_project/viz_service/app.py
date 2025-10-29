"""
Servicio de Visualización y Estadísticas
Tarea 2 - Sistemas Distribuidos

Dashboard web para visualizar:
- Scores de Flink (BERTScore)
- Distribución de scores
- Estadísticas temporales
- Métricas del sistema
"""

from flask import Flask, render_template, jsonify
import psycopg2
import os
import logging
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@postgres:5432/yahoo_db')

def get_db_connection():
    """Crear conexión a PostgreSQL"""
    return psycopg2.connect(DATABASE_URL)

@app.route('/')
def index():
    """Página principal del dashboard"""
    return render_template('dashboard.html')

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Obtener estadísticas generales"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total de respuestas
        cursor.execute("SELECT COUNT(*) FROM responses")
        total_responses = cursor.fetchone()[0]
        
        # Score promedio general
        cursor.execute("""
            SELECT AVG(bert_score) 
            FROM responses 
            WHERE bert_score IS NOT NULL
        """)
        avg_score = cursor.fetchone()[0]
        
        # Score mínimo y máximo
        cursor.execute("""
            SELECT MIN(bert_score), MAX(bert_score) 
            FROM responses 
            WHERE bert_score IS NOT NULL
        """)
        min_score, max_score = cursor.fetchone()
        
        # Distribución por rangos de score
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN bert_score < 0.50 THEN '0.0-0.5'
                    WHEN bert_score < 0.60 THEN '0.5-0.6'
                    WHEN bert_score < 0.70 THEN '0.6-0.7'
                    WHEN bert_score < 0.75 THEN '0.7-0.75'
                    WHEN bert_score < 0.80 THEN '0.75-0.8'
                    WHEN bert_score < 0.90 THEN '0.8-0.9'
                    ELSE '0.9-1.0'
                END as score_range,
                COUNT(*) as count
            FROM responses
            WHERE bert_score IS NOT NULL
            GROUP BY score_range
            ORDER BY score_range
        """)
        score_distribution = [
            {'range': row[0], 'count': row[1]} 
            for row in cursor.fetchall()
        ]
        
        # Respuestas por intentos de procesamiento
        cursor.execute("""
            SELECT processing_attempts, COUNT(*) 
            FROM responses 
            GROUP BY processing_attempts 
            ORDER BY processing_attempts
        """)
        attempts_distribution = [
            {'attempts': row[0], 'count': row[1]} 
            for row in cursor.fetchall()
        ]
        
        # Tiempo promedio de procesamiento
        cursor.execute("""
            SELECT AVG(total_processing_time_ms) 
            FROM responses 
            WHERE total_processing_time_ms IS NOT NULL
        """)
        avg_processing_time = cursor.fetchone()[0]
        
        # Respuestas en las últimas 24 horas
        cursor.execute("""
            SELECT COUNT(*) 
            FROM responses 
            WHERE created_at >= NOW() - INTERVAL '24 hours'
        """)
        responses_24h = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'total_responses': total_responses,
            'avg_score': float(avg_score) if avg_score else 0,
            'min_score': float(min_score) if min_score else 0,
            'max_score': float(max_score) if max_score else 0,
            'score_distribution': score_distribution,
            'attempts_distribution': attempts_distribution,
            'avg_processing_time_ms': float(avg_processing_time) if avg_processing_time else 0,
            'responses_24h': responses_24h
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/scores/timeseries', methods=['GET'])
def get_scores_timeseries():
    """Obtener serie temporal de scores"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Scores por hora en las últimas 24 horas
        cursor.execute("""
            SELECT 
                DATE_TRUNC('hour', created_at) as hour,
                AVG(bert_score) as avg_score,
                COUNT(*) as count
            FROM responses
            WHERE created_at >= NOW() - INTERVAL '24 hours'
                AND bert_score IS NOT NULL
            GROUP BY hour
            ORDER BY hour
        """)
        
        timeseries = [
            {
                'timestamp': row[0].isoformat(),
                'avg_score': float(row[1]),
                'count': row[2]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        conn.close()
        
        return jsonify(timeseries), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo serie temporal: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/scores/histogram', methods=['GET'])
def get_scores_histogram():
    """Obtener histograma detallado de scores"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Histograma con bins de 0.05
        cursor.execute("""
            SELECT 
                FLOOR(bert_score * 20) / 20 as bin_start,
                COUNT(*) as count
            FROM responses
            WHERE bert_score IS NOT NULL
            GROUP BY bin_start
            ORDER BY bin_start
        """)
        
        histogram = [
            {
                'bin_start': float(row[0]),
                'bin_end': float(row[0]) + 0.05,
                'count': row[1]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        conn.close()
        
        return jsonify(histogram), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo histograma: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/questions/top', methods=['GET'])
def get_top_questions():
    """Obtener preguntas con mejor y peor score"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Top 10 mejores scores
        cursor.execute("""
            SELECT question_text, llm_response, bert_score, processing_attempts
            FROM responses
            WHERE bert_score IS NOT NULL
            ORDER BY bert_score DESC
            LIMIT 10
        """)
        
        top_scores = [
            {
                'question': row[0],
                'answer': row[1],
                'score': float(row[2]),
                'attempts': row[3]
            }
            for row in cursor.fetchall()
        ]
        
        # Top 10 peores scores
        cursor.execute("""
            SELECT question_text, llm_response, bert_score, processing_attempts
            FROM responses
            WHERE bert_score IS NOT NULL
            ORDER BY bert_score ASC
            LIMIT 10
        """)
        
        worst_scores = [
            {
                'question': row[0],
                'answer': row[1],
                'score': float(row[2]),
                'attempts': row[3]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'top_scores': top_scores,
            'worst_scores': worst_scores
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo top questions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/quality/improvement', methods=['GET'])
def get_quality_improvement():
    """Analizar mejora de calidad por reintentos"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Score promedio por número de intentos
        cursor.execute("""
            SELECT 
                processing_attempts,
                AVG(bert_score) as avg_score,
                COUNT(*) as count
            FROM responses
            WHERE bert_score IS NOT NULL
            GROUP BY processing_attempts
            ORDER BY processing_attempts
        """)
        
        improvement = [
            {
                'attempts': row[0],
                'avg_score': float(row[1]),
                'count': row[2]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        conn.close()
        
        return jsonify(improvement), 200
        
    except Exception as e:
        logger.error(f"Error analizando mejora: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        
        return jsonify({'status': 'healthy'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("📊 Servicio de Visualización iniciado")
    logger.info("=" * 60)
    app.run(host='0.0.0.0', port=5002, debug=False)
