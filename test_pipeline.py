import requests
import json
import time
import hashlib

STORAGE_SERVICE_URL = "http://localhost:5001"

def generate_question_id(question):
    """Genera un ID unico para la pregunta basado en SHA256."""
    return hashlib.sha256(question.encode('utf-8')).hexdigest()[:16]

def test_case_1_normal_flow():
    """Caso 1: Flujo normal - pregunta que funciona correctamente."""
    print("\n=== Caso 1: Flujo Normal ===")
    
    question = "¿Qué es Docker y para qué se utiliza?"
    question_id = generate_question_id(question)
    
    payload = {
        "question_text": question,
        "original_answer": "Tecnología de contenedores"
    }
    
    print(f"Enviando pregunta: {question}")
    response = requests.post(f"{STORAGE_SERVICE_URL}/query", json=payload)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 202:
        print("Consulta aceptada, esperando procesamiento...")
        time.sleep(5)
        
        status_response = requests.get(f"{STORAGE_SERVICE_URL}/status/{question_id}")
        print(f"Status final: {status_response.json()}")

def test_case_2_cache_hit():
    """Caso 2: Cache hit - pregunta ya procesada."""
    print("\n=== Caso 2: Cache Hit ===")
    
    question = "¿Qué es Docker y para qué se utiliza?"
    
    payload = {
        "question_text": question,
        "original_answer": "Tecnología de contenedores"
    }
    
    print(f"Enviando pregunta repetida: {question}")
    response = requests.post(f"{STORAGE_SERVICE_URL}/query", json=payload)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

def test_case_3_metrics():
    """Caso 3: Consultar metricas del sistema."""
    print("\n=== Caso 3: Metricas del Sistema ===")
    
    response = requests.get(f"{STORAGE_SERVICE_URL}/metrics")
    
    print(f"Status: {response.status_code}")
    metrics = response.json()
    
    print(json.dumps(metrics, indent=2))

def main():
    print("Iniciando pruebas del sistema...")
    print(f"URL del Storage Service: {STORAGE_SERVICE_URL}")
    
    try:
        test_case_1_normal_flow()
        time.sleep(2)
        
        test_case_2_cache_hit()
        time.sleep(2)
        
        test_case_3_metrics()
        
        print("\n=== Pruebas completadas ===")
        
    except requests.exceptions.ConnectionError:
        print("Error: No se pudo conectar al Storage Service")
        print("Asegurate de que docker-compose este ejecutandose")
    except Exception as e:
        print(f"Error inesperado: {str(e)}")

if __name__ == "__main__":
    main()
