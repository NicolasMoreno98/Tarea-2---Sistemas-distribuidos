import os
import json
import time
import logging
from kafka import KafkaConsumer, KafkaProducer
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'kafka:9092')
CONSUMER_GROUP = 'retry-overload-consumer-group'
MAX_RETRIES = 3

def init_kafka():
    """Inicializa consumer y producer de Kafka."""
    consumer = KafkaConsumer(
        'llm-responses-error-overload',
        bootstrap_servers=[KAFKA_BROKER],
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='earliest',
        enable_auto_commit=True
    )
    
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_BROKER],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    logger.info(f"Conectado a Kafka: {KAFKA_BROKER}")
    return consumer, producer

def calculate_backoff_delay(retry_count):
    """
    Calcula delay con exponential backoff: 2^retry_count segundos.
    retry_count=0 -> 1s
    retry_count=1 -> 2s
    retry_count=2 -> 4s
    """
    return 2 ** retry_count

def process_error_message(producer, message):
    """
    Procesa mensaje de error de overload.
    Aplica exponential backoff y reintenta si no se alcanzo el maximo.
    """
    question_id = message.get('question_id')
    retry_count = message.get('retry_count', 0)
    error_code = message.get('error_code')
    
    if retry_count >= MAX_RETRIES:
        logger.warning(f"Pregunta {question_id} alcanzó máximo de reintentos ({MAX_RETRIES})")
        
        failed_message = {
            'question_id': question_id,
            'question': message.get('question'),
            'context': message.get('context'),
            'retry_count': retry_count,
            'final_status': 'failed_max_retries',
            'error_code': error_code,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            producer.send('llm-responses-error-permanent', failed_message)
            logger.info(f"Mensaje de fallo permanente enviado para {question_id}")
        except Exception as e:
            logger.error(f"Error enviando fallo permanente: {str(e)}")
        
        return
    
    delay = calculate_backoff_delay(retry_count)
    logger.info(f"Aplicando backoff para {question_id}: {delay}s (intento {retry_count + 1}/{MAX_RETRIES})")
    
    time.sleep(delay)
    
    retry_message = {
        'question_id': question_id,
        'question': message.get('question'),
        'context': message.get('context'),
        'retry_count': retry_count + 1,
        'previous_error': error_code,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    try:
        producer.send('questions-pending', retry_message)
        logger.info(f"Reintento {retry_count + 1} enviado para {question_id}")
    except Exception as e:
        logger.error(f"Error enviando reintento: {str(e)}")

def main():
    """Loop principal del retry consumer."""
    logger.info("Iniciando Retry Overload Consumer...")
    
    max_connection_retries = 5
    retry_delay = 5
    
    for attempt in range(max_connection_retries):
        try:
            consumer, producer = init_kafka()
            break
        except Exception as e:
            if attempt < max_connection_retries - 1:
                logger.warning(f"Error conectando (intento {attempt + 1}): {str(e)}")
                time.sleep(retry_delay)
            else:
                logger.error("No se pudo conectar a Kafka")
                return
    
    logger.info("Retry Overload Consumer listo")
    
    try:
        for message in consumer:
            try:
                process_error_message(producer, message.value)
            except Exception as e:
                logger.error(f"Error procesando mensaje: {str(e)}")
                continue
                
    except KeyboardInterrupt:
        logger.info("Deteniendo Retry Overload Consumer...")
    finally:
        consumer.close()
        producer.close()
        logger.info("Retry Overload Consumer detenido")

if __name__ == "__main__":
    main()
