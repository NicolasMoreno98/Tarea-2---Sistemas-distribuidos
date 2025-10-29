#!/usr/bin/env python3
import hashlib
import sys

# Leer el texto de stdin
text = sys.stdin.read().strip()

# Generar SHA256 hash (primeros 16 caracteres)
question_id = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

# Imprimir solo el hash
print(question_id)
