-- Crear tabla para almacenar las respuestas
CREATE TABLE IF NOT EXISTS responses (
    id VARCHAR(50) PRIMARY KEY,
    question TEXT NOT NULL,
    human_answer TEXT,
    llm_answer TEXT,
    score FLOAT,
    count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índices para mejorar rendimiento
CREATE INDEX IF NOT EXISTS idx_responses_score ON responses(score);
CREATE INDEX IF NOT EXISTS idx_responses_count ON responses(count);
CREATE INDEX IF NOT EXISTS idx_responses_created_at ON responses(created_at);
