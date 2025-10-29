-- Script simplificado para actualizar question_id y eliminar duplicados
-- Ejecutar con: docker exec postgres_db psql -U user -d yahoo_db -f /tmp/fix_ids.sql

\echo '============================================================'
\echo '  FIX QUESTION_ID - Actualizar y Eliminar Duplicados'
\echo '============================================================'
\echo ''

-- Estadísticas ANTES
\echo '📊 ESTADÍSTICAS ANTES:'
SELECT 
    COUNT(*) as total_registros,
    COUNT(DISTINCT question_text) as textos_unicos,
    COUNT(DISTINCT question_id) as ids_unicos,
    COUNT(*) - COUNT(DISTINCT question_text) as duplicados_texto
FROM responses;

\echo ''
\echo '🔄 PROCESANDO...'
\echo ''

-- Crear tabla temporal con nuevos IDs (usando MD5 que está disponible en PostgreSQL)
CREATE TEMP TABLE temp_fix AS
WITH ranked AS (
    SELECT 
        question_id as old_id,
        SUBSTRING(MD5(question_text), 1, 16) as new_id,
        question_text,
        created_at,
        ROW_NUMBER() OVER (PARTITION BY question_text ORDER BY created_at DESC) as rn
    FROM responses
)
SELECT old_id, new_id, question_text, rn
FROM ranked;

-- IDs a eliminar (duplicados)
\echo 'Registros a eliminar:'
SELECT COUNT(*) as cantidad_duplicados FROM temp_fix WHERE rn > 1;

-- Eliminar duplicados (mantener solo rn=1)
DELETE FROM responses
WHERE question_id IN (
    SELECT old_id FROM temp_fix WHERE rn > 1
);

\echo 'Registros eliminados: ' || (SELECT COUNT(*) FROM temp_fix WHERE rn > 1);
\echo ''

-- Actualizar question_id para los que se mantienen
UPDATE responses r
SET question_id = t.new_id
FROM temp_fix t
WHERE r.question_id = t.old_id AND t.rn = 1;

\echo 'Registros actualizados: ' || (SELECT COUNT(*) FROM temp_fix WHERE rn = 1);
\echo ''

-- Estadísticas DESPUÉS
\echo '📊 ESTADÍSTICAS DESPUÉS:'
SELECT 
    COUNT(*) as total_registros,
    COUNT(DISTINCT question_text) as textos_unicos,
    COUNT(DISTINCT question_id) as ids_unicos
FROM responses;

\echo ''
\echo '✅ Verificación final:'
SELECT 
    CASE 
        WHEN COUNT(*) = COUNT(DISTINCT question_id) AND 
             COUNT(*) = COUNT(DISTINCT question_text) 
        THEN '✅ OK: Todos los registros son únicos'
        ELSE '⚠️  ERROR: Aún hay duplicados'
    END as resultado
FROM responses;

\echo ''
\echo '📋 EJEMPLOS (últimos 5 registros):'
SELECT 
    question_id,
    LEFT(question_text, 60) as texto,
    bert_score,
    TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') as fecha
FROM responses
ORDER BY created_at DESC
LIMIT 5;

\echo ''
\echo '✅ PROCESO COMPLETADO'
