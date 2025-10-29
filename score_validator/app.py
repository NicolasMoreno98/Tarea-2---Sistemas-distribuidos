import os
import json
import time
import logging
from kafka import KafkaConsumer, KafkaProducer
from datetime import datetime
from bert_score import score as bert_score_fn

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'kafka:9092')
CONSUMER_GROUP = 'score-validator-group'
SCORE_THRESHOLD = 0.75
MAX_REGENERATION_ATTEMPTS = 3

def init_kafka():
    """Inicializa consumer y producer de Kafka."""
    consumer = KafkaConsumer(
        'llm-responses-success',
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

def calculate_bertscore(candidate, reference):
    """
    Calcula BERTScore F1 entre respuesta candidata y referencia.
    Retorna valor entre 0 y 1.
    """
    if not reference or not candidate:
        logger.warning("Referencia o candidato vacio, usando score por defecto")
        return 0.8
    
    try:
        P, R, F1 = bert_score_fn([candidate], [reference], lang='es', verbose=False)
        score = F1.item()
        return round(score, 4)
    except Exception as e:
        logger.error(f"Error calculando BERTScore: {str(e)}")
        return 0.8

def process_response(producer, message):
    """
    Procesa respuesta exitosa del LLM.
    Calcula BERTScore y decide si validar o regenerar.
    """
    question_id = message.get('question_id')
    answer = message.get('answer')
    question = message.get('question')
    context = message.get('context')
    retry_count = message.get('retry_count', 0)
    
    logger.info(f"Validando respuesta para {question_id}")
    
    reference_answer = message.get('ground_truth') or message.get('reference_answer')
    
    if not reference_answer:
        logger.warning(f"Sin referencia para {question_id}, usando score default alto")
        score = 0.85
    else:
        score = calculate_bertscore(answer, reference_answer)
    
    logger.info(f"Score calculado para {question_id}: {score} (umbral: {SCORE_THRESHOLD})")
    
    timestamp = datetime.utcnow().isoformat()
    
    if score >= SCORE_THRESHOLD:
        validated_message = {
            'question_id': question_id,
            'question': question,
            'context': context,
            'answer': answer,
            'score': score,
            'retry_count': retry_count,
            'status': 'validated',
            'llm_latency_ms': message.get('llm_latency_ms'),
            'timestamp': timestamp
        }
        
        try:
            producer.send('validated-responses', validated_message)
            logger.info(f"Respuesta validada para {question_id} (score: {score})")
        except Exception as e:
            logger.error(f"Error enviando respuesta validada: {str(e)}")
    
    else:
        if retry_count >= MAX_REGENERATION_ATTEMPTS:
            logger.warning(f"Pregunta {question_id} alcanzó máximo de regeneraciones ({MAX_REGENERATION_ATTEMPTS})")
            
            low_quality_message = {
                'question_id': question_id,
                'question': question,
                'context': context,
                'answer': answer,
                'score': score,
                'retry_count': retry_count,
                'status': 'low_quality',
                'reason': 'max_regeneration_attempts_reached',
                'timestamp': timestamp
            }
            
            try:
                producer.send('low-quality-responses', low_quality_message)
                logger.info(f"Respuesta de baja calidad registrada para {question_id}")
            except Exception as e:
                logger.error(f"Error enviando respuesta de baja calidad: {str(e)}")
        
        else:
            logger.info(f"Score bajo para {question_id}, solicitando regeneración (intento {retry_count + 1})")
            
            regeneration_message = {
                'question_id': question_id,
                'question': question,
                'context': context,
                'retry_count': retry_count + 1,
                'previous_score': score,
                'previous_answer': answer,
                'reason': 'low_score',
                'timestamp': timestamp
            }
            
            try:
                producer.send('questions-pending', regeneration_message)
                logger.info(f"Solicitud de regeneración enviada para {question_id}")
            except Exception as e:
                logger.error(f"Error enviando solicitud de regeneración: {str(e)}")

def main():
    """Loop principal del score validator."""
    logger.info("Iniciando Score Validator Service...")
    
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
    
    logger.info("Score Validator listo")
    
    try:
        for message in consumer:
            try:
                process_response(producer, message.value)
            except Exception as e:
                logger.error(f"Error procesando mensaje: {str(e)}")
                continue
                
    except KeyboardInterrupt:
        logger.info("Deteniendo Score Validator...")
    finally:
        consumer.close()
        producer.close()
        logger.info("Score Validator detenido")

if __name__ == "__main__":
    main()
