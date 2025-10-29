-- Script para actualizar question_id basándose en hash del texto
-- y eliminar duplicados manteniendo el registro más reciente

-- Paso 1: Crear tabla temporal con los nuevos question_id
CREATE TEMP TABLE temp_new_ids AS
SELECT 
    question_id as old_id,
    SUBSTRING(MD5(question_text), 1, 16) as new_id,
    question_text,
    created_at,
    ROW_NUMBER() OVER (PARTITION BY question_text ORDER BY created_at DESC) as rn
FROM responses;

-- Paso 2: Ver estadísticas antes del cambio
SELECT 
    'ANTES DEL CAMBIO' as momento,
    COUNT(*) as total_registros,
    COUNT(DISTINCT question_text) as textos_unicos,
    COUNT(*) - COUNT(DISTINCT question_text) as duplicados
FROM responses;

-- Paso 3: Crear tabla temporal con IDs únicos a mantener
CREATE TEMP TABLE ids_to_keep AS
SELECT old_id, new_id
FROM temp_new_ids
WHERE rn = 1;

-- Paso 4: Ver cuántos registros se eliminarán
SELECT 
    'REGISTROS A ELIMINAR' as accion,
    COUNT(*) as cantidad
FROM responses r
WHERE question_id NOT IN (SELECT old_id FROM ids_to_keep);

-- Paso 5: Eliminar duplicados (mantener solo el más reciente por question_text)
DELETE FROM responses
WHERE question_id NOT IN (SELECT old_id FROM ids_to_keep);

-- Paso 6: Actualizar question_id con el hash del texto
UPDATE responses r
SET question_id = (
    SELECT new_id 
    FROM ids_to_keep itk 
    WHERE itk.old_id = r.question_id
);

-- Paso 7: Ver estadísticas después del cambio
SELECT 
    'DESPUES DEL CAMBIO' as momento,
    COUNT(*) as total_registros,
    COUNT(DISTINCT question_text) as textos_unicos,
    COUNT(DISTINCT question_id) as ids_unicos
FROM responses;

-- Paso 8: Verificar que no hay duplicados
SELECT 
    'VERIFICACION FINAL' as check_type,
    CASE 
        WHEN COUNT(*) = COUNT(DISTINCT question_id) THEN 'OK: Todos los question_id son únicos'
        ELSE 'ERROR: Hay question_id duplicados'
    END as resultado
FROM responses;

-- Paso 9: Mostrar algunos ejemplos de los cambios
SELECT 
    question_text,
    question_id as new_question_id,
    bert_score,
    created_at
FROM responses
ORDER BY created_at DESC
LIMIT 10;
