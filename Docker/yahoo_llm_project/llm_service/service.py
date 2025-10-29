import os
import json
import google.generativeai as genai
from flask import Flask, request, jsonify
import redis
import psycopg2
from bert_score import score

# Cargar API key
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("La variable de entorno GOOGLE_API_KEY no está configurada.")

genai.configure(api_key=api_key)

app = Flask(__name__)

# Configurar Redis
r = redis.Redis(host='redis', port=6379, db=0)

@app.route('/process', methods=['POST'])
def process_question():
    try:
        data = request.json
        question_id = data['id']
        question_text = data['question']
        human_answer = data['best_answer']
        
        # Verificar si está en cache
        cached_answer = r.get(f"answer:{question_id}")
        if cached_answer:
            # Actualizar contador
            r.incr(f"count:{question_id}")
            return jsonify({
                'source': 'cache', 
                'answer': cached_answer.decode(),
                'question_id': question_id
            })
        
        # Generar respuesta con Gemini 2.5 Flash (más actual y menos restrictivo)
        modelo = genai.GenerativeModel('gemini-2.5-flash')
        respuesta = modelo.generate_content(
            f"Responde de manera concisa y en español: {question_text}"
        )
        llm_answer = respuesta.text.strip()
        
        # Calcular score de similitud (BERTScore)
        P, R, F1 = score([llm_answer], [human_answer], lang="es")
        similarity_score = float(F1.mean())
        
        # Guardar en PostgreSQL
        save_to_database(question_id, question_text, human_answer, llm_answer, similarity_score)
        
        # Guardar en cache (1 hora de TTL)
        r.setex(f"answer:{question_id}", 3600, llm_answer)
        r.set(f"count:{question_id}", 1)
        
        return jsonify({
            'source': 'llm',
            'question_id': question_id,
            'answer': llm_answer,
            'score': similarity_score
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def save_to_database(question_id, question, human_ans, llm_ans, score):
    """Guarda los datos en PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host="postgres",
            database="yahoo_db",
            user="user",
            password="password"
        )
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO responses (id, question, human_answer, llm_answer, score, count)
            VALUES (%s, %s, %s, %s, %s, 1)
            ON CONFLICT (id) DO UPDATE SET count = responses.count + 1
        """, (question_id, question, human_ans, llm_ans, score))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error saving to database: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)