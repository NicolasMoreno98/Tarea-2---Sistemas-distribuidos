import json

# Cargar response.json y extraer los question_id
with open('dataset/response.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Extraer todos los question_id y convertirlos a enteros
question_ids = []
responses = data.get('responses', [])
for item in responses:
    try:
        qid = int(item['question_id'])
        question_ids.append(qid)
    except (ValueError, KeyError):
        continue

question_ids.sort()

print(f"Total de preguntas en response.json: {len(question_ids)}")
print(f"Rango de IDs: {min(question_ids)} - {max(question_ids)}")
print(f"\nPrimeros 50 IDs:")
print(question_ids[:50])

# Guardar los IDs en un archivo para usarlos en el traffic_generator
with open('dataset/cached_question_ids.txt', 'w') as f:
    for qid in question_ids:
        f.write(f"{qid}\n")

print(f"\n✓ IDs guardados en dataset/cached_question_ids.txt")
