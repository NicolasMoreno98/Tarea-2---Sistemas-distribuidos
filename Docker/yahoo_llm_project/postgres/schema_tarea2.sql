-- Schema para Tarea 2 con soporte para pipeline asíncrono
-- Incluye tablas para respuestas, reintentos fallidos y métricas

-- Tabla principal de respuestas procesadas
CREATE TABLE IF NOT EXISTS responses (
    question_id VARCHAR(16) PRIMARY KEY,
    question_text TEXT NOT NULL,
    llm_response TEXT,
    original_answer TEXT,
    bert_score FLOAT,
    processing_attempts INTEGER DEFAULT 1,
    total_processing_time_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla para registrar preguntas con fallos permanentes
CREATE TABLE IF NOT EXISTS failed_questions (
    id SERIAL PRIMARY KEY,
    question_id VARCHAR(16) NOT NULL,
    question_text TEXT NOT NULL,
    error_type VARCHAR(50),
    error_message TEXT,
    retry_count INTEGER,
    last_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(question_id)
);

-- Tabla para métricas de procesamiento
CREATE TABLE IF NOT EXISTS processing_metrics (
    id SERIAL PRIMARY KEY,
    question_id VARCHAR(16),
    stage VARCHAR(50) NOT NULL,  -- 'llm_request', 'flink_scoring', 'persistence'
    duration_ms INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Tabla para scores históricos (para análisis de mejora)
CREATE TABLE IF NOT EXISTS score_history (
    id SERIAL PRIMARY KEY,
    question_id VARCHAR(16) NOT NULL,
    attempt_number INTEGER,
    bert_score FLOAT,
    processing_time_ms INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para mejorar rendimiento
CREATE INDEX IF NOT EXISTS idx_responses_score ON responses(bert_score);
CREATE INDEX IF NOT EXISTS idx_responses_attempts ON responses(processing_attempts);
CREATE INDEX IF NOT EXISTS idx_responses_created_at ON responses(created_at);

CREATE INDEX IF NOT EXISTS idx_failed_questions_error_type ON failed_questions(error_type);
CREATE INDEX IF NOT EXISTS idx_failed_questions_attempt ON failed_questions(last_attempt_at);

CREATE INDEX IF NOT EXISTS idx_metrics_stage ON processing_metrics(stage);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON processing_metrics(timestamp);

CREATE INDEX IF NOT EXISTS idx_score_history_question ON score_history(question_id);
CREATE INDEX IF NOT EXISTS idx_score_history_timestamp ON score_history(timestamp);

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para actualizar updated_at en responses
CREATE TRIGGER update_responses_updated_at BEFORE UPDATE ON responses
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Vista para análisis de mejoras por regeneración
CREATE OR REPLACE VIEW regeneration_analysis AS
SELECT 
    r.question_id,
    r.processing_attempts,
    r.bert_score as final_score,
    sh_first.bert_score as first_score,
    (r.bert_score - sh_first.bert_score) as score_improvement,
    r.total_processing_time_ms,
    r.created_at
FROM responses r
LEFT JOIN LATERAL (
    SELECT bert_score 
    FROM score_history 
    WHERE question_id = r.question_id 
    AND attempt_number = 1 
    LIMIT 1
) sh_first ON true
WHERE r.processing_attempts > 1;

-- Vista para distribución de errores
CREATE OR REPLACE VIEW error_distribution AS
SELECT 
    error_type,
    COUNT(*) as count,
    AVG(retry_count) as avg_retries,
    MAX(last_attempt_at) as last_occurrence
FROM failed_questions
GROUP BY error_type
ORDER BY count DESC;

-- Vista para métricas de latencia por etapa
CREATE OR REPLACE VIEW latency_by_stage AS
SELECT 
    stage,
    COUNT(*) as operations,
    AVG(duration_ms) as avg_latency_ms,
    MIN(duration_ms) as min_latency_ms,
    MAX(duration_ms) as max_latency_ms,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms) as p50_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_latency_ms,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) as p99_latency_ms
FROM processing_metrics
GROUP BY stage
ORDER BY avg_latency_ms DESC;
