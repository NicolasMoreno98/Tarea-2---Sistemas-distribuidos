"""
Servicio de Almacenamiento con Kafka
Tarea 2 - Sistemas Distribuidos

Este módulo actúa como punto de entrada para consultas y como persistencia final.
Roles:
- Consulta PostgreSQL primero (con caché Redis)
- Si no existe, produce mensaje a Kafka (questions-pending)
- Consume mensajes validados de Kafka (validated-responses) y persiste
"""

from flask import Flask, request, jsonify
import psycopg2
import redis
import json
import hashlib
import uuid
from datetime import datetime
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import threading
import os
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuración desde variables de entorno
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@postgres:5432/yahoo_db')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092').split(',')

# Conexiones
db_conn = None
redis_client = None
kafka_producer = None
kafka_consumer = None

def init_connections():
    """Inicializar conexiones a PostgreSQL, Redis y Kafka"""
    global db_conn, redis_client, kafka_producer, kafka_consumer
    
    # PostgreSQL
    try:
        db_conn = psycopg2.connect(DATABASE_URL)
        logger.info("✓ Conectado a PostgreSQL")
    except Exception as e:
        logger.error(f"✗ Error conectando a PostgreSQL: {e}")
        raise
    
    # Redis
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        logger.info("✓ Conectado a Redis")
    except Exception as e:
        logger.error(f"✗ Error conectando a Redis: {e}")
        raise
    
    # Kafka Producer
    try:
        kafka_producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',
            retries=3,
            max_in_flight_requests_per_connection=1
        )
        logger.info("✓ Kafka Producer inicializado")
    except Exception as e:
        logger.error(f"✗ Error inicializando Kafka Producer: {e}")
        raise
    
    # Kafka Consumer (en thread separado)
    try:
        kafka_consumer = KafkaConsumer(
            'validated-responses',
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            group_id='storage-consumer-group',
            auto_offset_reset='earliest',
            enable_auto_commit=True
        )
        logger.info("✓ Kafka Consumer inicializado")
        
        # Iniciar consumidor en thread separado
        consumer_thread = threading.Thread(target=consume_validated_responses, daemon=True)
        consumer_thread.start()
        logger.info("✓ Thread consumidor iniciado")
    except Exception as e:
        logger.error(f"✗ Error inicializando Kafka Consumer: {e}")
        raise

def generate_question_id(question_text):
    """Generar ID único basado en hash del texto de la pregunta"""
    return hashlib.sha256(question_text.encode('utf-8')).hexdigest()[:16]

def check_cache(question_id):
    """Verificar si existe respuesta en caché Redis"""
    try:
        cached = redis_client.get(f"question:{question_id}")
        if cached:
            logger.info(f"✓ Cache HIT para question_id={question_id}")
            return json.loads(cached)
        logger.info(f"✗ Cache MISS para question_id={question_id}")
        return None
    except Exception as e:
        logger.warning(f"Error en caché Redis: {e}")
        return None

def check_database(question_id):
    """Verificar si existe respuesta en PostgreSQL"""
    try:
        cursor = db_conn.cursor()
        cursor.execute(
            """
            SELECT question_text, llm_response, original_answer, 
                   bert_score, processing_attempts, created_at
            FROM responses
            WHERE question_id = %s
            """,
            (question_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            result = {
                'question_id': question_id,
                'question_text': row[0],
                'llm_response': row[1],
                'original_answer': row[2],
                'bert_score': float(row[3]) if row[3] else None,
                'processing_attempts': row[4],
                'created_at': row[5].isoformat() if row[5] else None,
                'source': 'database'
            }
            logger.info(f"✓ Database HIT para question_id={question_id}")
            
            # Popular caché
            redis_client.setex(
                f"question:{question_id}",
                3600,  # TTL 1 hora
                json.dumps(result)
            )
            
            return result
        
        logger.info(f"✗ Database MISS para question_id={question_id}")
        return None
    except Exception as e:
        logger.error(f"Error consultando PostgreSQL: {e}")
        return None

def produce_to_kafka(question_id, question_text, original_answer=None):
    """Enviar pregunta a Kafka para procesamiento asíncrono"""
    try:
        message = {
            'question_id': question_id,
            'question_text': question_text,
            'original_answer': original_answer,
            'retry_count': 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        future = kafka_producer.send(
            'questions-pending',
            key=question_id,
            value=message
        )
        
        # Esperar confirmación
        record_metadata = future.get(timeout=10)
        logger.info(
            f"✓ Mensaje enviado a Kafka: topic={record_metadata.topic}, "
            f"partition={record_metadata.partition}, offset={record_metadata.offset}"
        )
        
        return True
    except KafkaError as e:
        logger.error(f"✗ Error enviando a Kafka: {e}")
        return False

def persist_response(message):
    """Persistir respuesta validada en PostgreSQL"""
    try:
        # Extraer campos con nombres flexibles
        question_id = message.get('question_id')
        question_text = message.get('question_text') or message.get('question')
        answer = message.get('answer') or message.get('llm_response')
        original_answer = message.get('original_answer') or message.get('context')
        score = message.get('score') or message.get('bert_score')
        attempts = message.get('retry_count', 0) + 1  # retry_count + 1 = total attempts
        latency = message.get('llm_latency_ms') or message.get('total_processing_time_ms', 0)
        
        cursor = db_conn.cursor()
        cursor.execute(
            """
            INSERT INTO responses (
                question_id, question_text, llm_response, original_answer,
                bert_score, processing_attempts, total_processing_time_ms, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (question_id) DO UPDATE SET
                llm_response = EXCLUDED.llm_response,
                bert_score = EXCLUDED.bert_score,
                processing_attempts = EXCLUDED.processing_attempts,
                total_processing_time_ms = EXCLUDED.total_processing_time_ms,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                question_id,
                question_text,
                answer,
                original_answer,
                score,
                attempts,
                latency,
                datetime.utcnow()
            )
        )
        db_conn.commit()
        cursor.close()
        
        logger.info(f"✓ Respuesta persistida en PostgreSQL: {question_id}")
        
        # Actualizar caché
        cache_data = {
            'question_id': question_id,
            'question_text': question_text,
            'answer': answer,
            'score': score
        }
        redis_client.setex(
            f"question:{question_id}",
            3600,
            json.dumps(cache_data)
        )
        
        return True
    except Exception as e:
        db_conn.rollback()
        logger.error(f"✗ Error persistiendo en PostgreSQL: {e}")
        return False

def consume_validated_responses():
    """Thread consumidor para mensajes de validated-responses"""
    logger.info("→ Iniciando consumo de validated-responses...")
    
    try:
        for message in kafka_consumer:
            try:
                validated_response = message.value
                logger.info(
                    f"← Mensaje recibido de Kafka: "
                    f"question_id={validated_response['question_id']}"
                )
                
                # Persistir en base de datos
                persist_response(validated_response)
                
            except Exception as e:
                logger.error(f"✗ Error procesando mensaje: {e}")
                continue
    except Exception as e:
        logger.error(f"✗ Error en consumidor Kafka: {e}")

# ==================== ENDPOINTS HTTP ====================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Verificar PostgreSQL
        cursor = db_conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        
        # Verificar Redis
        redis_client.ping()
        
        # Verificar Kafka Producer
        kafka_producer.bootstrap_connected()
        
        return jsonify({
            'status': 'healthy',
            'services': {
                'postgresql': 'ok',
                'redis': 'ok',
                'kafka_producer': 'ok',
                'kafka_consumer': 'ok'
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/query', methods=['POST'])
def query_question():
    """
    Endpoint principal para consultar/procesar preguntas
    
    Flujo:
    1. Buscar en caché Redis
    2. Buscar en PostgreSQL
    3. Si no existe, enviar a Kafka para procesamiento asíncrono
    """
    try:
        data = request.json
        question_text = data.get('question_text')
        original_answer = data.get('original_answer')
        
        if not question_text:
            return jsonify({'error': 'question_text es requerido'}), 400
        
        # Generar question_id único
        question_id = generate_question_id(question_text)
        
        # 1. Verificar caché
        cached_result = check_cache(question_id)
        if cached_result:
            return jsonify({
                'status': 'found',
                'source': 'cache',
                'result': cached_result
            }), 200
        
        # 2. Verificar base de datos
        db_result = check_database(question_id)
        if db_result:
            return jsonify({
                'status': 'found',
                'source': 'database',
                'result': db_result
            }), 200
        
        # 3. No existe → Enviar a Kafka
        success = produce_to_kafka(question_id, question_text, original_answer)
        
        if success:
            return jsonify({
                'status': 'pending',
                'question_id': question_id,
                'message': 'Pregunta enviada para procesamiento asíncrono'
            }), 202  # 202 Accepted
        else:
            return jsonify({
                'status': 'error',
                'message': 'Error enviando pregunta a Kafka'
            }), 500
            
    except Exception as e:
        logger.error(f"Error en /query: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/status/<question_id>', methods=['GET'])
def check_status(question_id):
    """
    Verificar estado de procesamiento de una pregunta
    """
    try:
        # Verificar caché primero
        cached = check_cache(question_id)
        if cached:
            return jsonify({
                'status': 'completed',
                'result': cached
            }), 200
        
        # Verificar base de datos
        db_result = check_database(question_id)
        if db_result:
            return jsonify({
                'status': 'completed',
                'result': db_result
            }), 200
        
        # No encontrado → Aún pendiente
        return jsonify({
            'status': 'pending',
            'message': 'Pregunta en procesamiento'
        }), 202
        
    except Exception as e:
        logger.error(f"Error en /status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Endpoint para métricas del sistema"""
    try:
        cursor = db_conn.cursor()
        
        # Total de preguntas procesadas
        cursor.execute("SELECT COUNT(*) FROM responses")
        total_responses = cursor.fetchone()[0]
        
        # Score promedio
        cursor.execute("SELECT AVG(bert_score) FROM responses WHERE bert_score IS NOT NULL")
        avg_score = cursor.fetchone()[0]
        
        # Distribución de intentos
        cursor.execute("""
            SELECT processing_attempts, COUNT(*) 
            FROM responses 
            GROUP BY processing_attempts 
            ORDER BY processing_attempts
        """)
        attempts_distribution = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.close()
        
        return jsonify({
            'total_responses': total_responses,
            'average_score': float(avg_score) if avg_score else None,
            'attempts_distribution': attempts_distribution,
            'cache_info': redis_client.info('stats')
        }), 200
        
    except Exception as e:
        logger.error(f"Error en /metrics: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    try:
        init_connections()
        logger.info("=" * 60)
        logger.info("🚀 Storage Service iniciado correctamente")
        logger.info("=" * 60)
        app.run(host='0.0.0.0', port=5001, debug=False)
    except Exception as e:
        logger.error(f"✗ Error fatal al iniciar Storage Service: {e}")
        exit(1)
