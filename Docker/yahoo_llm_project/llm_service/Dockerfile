FROM python:3.9-slim

WORKDIR /app

# Copiar requirements primero (para cache de Docker)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copiar el código para Ollama (no necesitamos key.env)
COPY service_ollama.py .
CMD ["python", "service_ollama.py"]