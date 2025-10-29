import os
import sys
import json
import time
import logging
import requests
from kafka import KafkaConsumer, KafkaProducer
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'kafka:9092')
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://host.docker.internal:11434')
CONSUMER_GROUP = os.environ.get('CONSUMER_GROUP', 'llm-consumer-group')
MODEL_NAME = os.environ.get('MODEL_NAME', 'tinyllama')

def init_kafka():
    """Inicializa los clientes de Kafka."""
    consumer = KafkaConsumer(
        'questions-pending',
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
    
    logger.info(f"Conectado a Kafka broker: {KAFKA_BROKER}")
    logger.info(f"Consumiendo del topico: questions-pending")
    return consumer, producer

def call_llm(question, context=None):
    """
    Realiza llamada al LLM via Ollama API.
    Retorna (status_code, response_text, latency_ms)
    """
    start_time = time.time()
    
    prompt = question
    if context:
        prompt = f"Contexto: {context}\n\nPregunta: {question}"
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "max_tokens": 500
        }
    }
    
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=30
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('response', '').strip()
            return response.status_code, answer, latency_ms
        else:
            return response.status_code, None, latency_ms
            
    except requests.exceptions.Timeout:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Timeout llamando al LLM: {question[:50]}")
        return 503, None, latency_ms
        
    except requests.exceptions.ConnectionError:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Error de conexion con LLM: {question[:50]}")
        return 503, None, latency_ms
        
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Error inesperado: {str(e)}")
        return 500, None, latency_ms

def produce_response(producer, topic, message):
    """Produce mensaje a un topico especifico de Kafka."""
    try:
        future = producer.send(topic, message)
        future.get(timeout=10)
        logger.info(f"Mensaje enviado a {topic}: question_id={message.get('question_id')}")
    except Exception as e:
        logger.error(f"Error produciendo a {topic}: {str(e)}")

def process_question(producer, message):
    """
    Procesa una pregunta del topico questions-pending.
    Clasifica la respuesta segun el status code y produce al topico correspondiente.
    """
    if not message:
        logger.error("Mensaje vacio recibido")
        return
        
    question_id = message.get('question_id')
    question = message.get('question_text') or message.get('question')
    context = message.get('context') or message.get('original_answer')
    retry_count = message.get('retry_count', 0)
    
    if not question_id or not question:
        logger.error(f"Mensaje invalido: {message}")
        return
    
    logger.info(f"Procesando pregunta {question_id} (intento {retry_count + 1}): {question[:60]}")
    
    status_code, answer, latency_ms = call_llm(question, context)
    
    timestamp = datetime.utcnow().isoformat()
    
    base_response = {
        'question_id': question_id,
        'question': question,
        'context': context,
        'retry_count': retry_count,
        'llm_latency_ms': latency_ms,
        'timestamp': timestamp
    }
    
    if status_code == 200:
        response = {
            **base_response,
            'answer': answer,
            'status': 'success'
        }
        produce_response(producer, 'llm-responses-success', response)
        logger.info(f"Respuesta exitosa para {question_id} (latencia: {latency_ms}ms)")
        
    elif status_code in [503, 429]:
        response = {
            **base_response,
            'status': 'error_overload',
            'error_code': status_code,
            'error_message': 'Service overloaded or rate limited'
        }
        produce_response(producer, 'llm-responses-error-overload', response)
        logger.warning(f"Error overload para {question_id}: status {status_code}")
        
    elif status_code == 402:
        response = {
            **base_response,
            'status': 'error_quota',
            'error_code': status_code,
            'error_message': 'Quota exceeded'
        }
        produce_response(producer, 'llm-responses-error-quota', response)
        logger.warning(f"Error quota para {question_id}")
        
    else:
        response = {
            **base_response,
            'status': 'error_unknown',
            'error_code': status_code,
            'error_message': f'Unexpected error: {status_code}'
        }
        produce_response(producer, 'llm-responses-error-overload', response)
        logger.error(f"Error desconocido para {question_id}: status {status_code}")

def main():
    """Loop principal del consumidor."""
    logger.info("Iniciando LLM Consumer Service...")
    
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            consumer, producer = init_kafka()
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Error conectando a Kafka (intento {attempt + 1}/{max_retries}): {str(e)}")
                time.sleep(retry_delay)
            else:
                logger.error("No se pudo conectar a Kafka despues de multiples intentos")
                sys.exit(1)
    
    logger.info("LLM Consumer listo para procesar mensajes")
    
    try:
        for message in consumer:
            try:
                # Logging defensivo
                if message is None:
                    logger.warning("Mensaje None recibido del consumer")
                    continue
                    
                if not hasattr(message, 'value'):
                    logger.warning(f"Mensaje sin atributo 'value': {type(message)}")
                    continue
                
                msg_value = message.value
                if msg_value is None:
                    logger.warning("message.value es None")
                    continue
                    
                logger.info(f"Mensaje recibido: topic={message.topic}, partition={message.partition}, offset={message.offset}")
                logger.info(f"Contenido del mensaje: {msg_value}")
                
                process_question(producer, msg_value)
            except Exception as e:
                logger.error(f"Error procesando mensaje: {str(e)}", exc_info=True)
                continue
                
    except KeyboardInterrupt:
        logger.info("Deteniendo LLM Consumer...")
    finally:
        consumer.close()
        producer.close()
        logger.info("LLM Consumer detenido")

if __name__ == "__main__":
    main()
