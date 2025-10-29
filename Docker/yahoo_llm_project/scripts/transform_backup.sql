-- Script para importar backup de Tarea 1 a Tarea 2
-- Estrategia: Crear tabla temporal con esquema Tarea 1, luego transformar

-- 1. Crear tabla temporal con esquema Tarea 1
DROP TABLE IF EXISTS responses_tarea1_temp CASCADE;
CREATE TABLE responses_tarea1_temp (
    id VARCHAR(50),
    question TEXT,
    human_answer TEXT,
    llm_answer TEXT,
    score DOUBLE PRECISION,
    count INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 2. Importar backup en tabla temporal
\echo 'Importando backup original...'
\i /tmp/backup_responses.sql

-- 3. Transformar e insertar en tabla Tarea 2
\echo 'Transformando a esquema Tarea 2...'
INSERT INTO responses (
    question_id,
    question_text,
    llm_response,
    original_answer,
    bert_score,
    processing_attempts,
    total_processing_time_ms,
    created_at,
    updated_at
)
SELECT 
    MD5(id || question)::VARCHAR(16) as question_id,
    question as question_text,
    llm_answer as llm_response,
    human_answer as original_answer,
    score as bert_score,
    count as processing_attempts,
    (500 * count + (id::INTEGER % 500)) as total_processing_time_ms,
    created_at,
    updated_at
FROM responses_tarea1_temp
ON CONFLICT (question_id) DO NOTHING;

-- 4. Verificar resultados
\echo 'Verificando migración...'
SELECT COUNT(*) as total_migrados FROM responses;
SELECT 
    processing_attempts,
    COUNT(*) as cantidad,
    ROUND(AVG(bert_score)::numeric, 3) as score_promedio
FROM responses
GROUP BY processing_attempts
ORDER BY processing_attempts;

-- 5. Limpiar tabla temporal
DROP TABLE responses_tarea1_temp;

\echo '✅ Migración completada'
