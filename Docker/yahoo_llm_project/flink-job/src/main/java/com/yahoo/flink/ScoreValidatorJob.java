package com.yahoo.flink;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.ProcessFunction;
import org.apache.flink.util.Collector;
import org.apache.hc.client5.http.classic.methods.HttpPost;
import org.apache.hc.client5.http.impl.classic.CloseableHttpClient;
import org.apache.hc.client5.http.impl.classic.CloseableHttpResponse;
import org.apache.hc.client5.http.impl.classic.HttpClients;
import org.apache.hc.core5.http.io.entity.StringEntity;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

/**
 * Trabajo Flink para validación de calidad de respuestas LLM
 * 
 * Funcionalidad:
 * 1. Consume respuestas exitosas del LLM desde 'llm-responses-success'
 * 2. Calcula BERTScore usando el servicio score_validator
 * 3. Si score < 0.85: reinyecta pregunta a 'questions-pending' para regeneración
 * 4. Si score >= 0.85: publica a 'validated-responses' para persistencia
 * 5. Previene ciclos infinitos limitando a 3 reintentos por pregunta
 * 
 * UMBRAL 0.85: Basado en análisis de 7,887 respuestas (mediana de distribución)
 * - Balance óptimo: 50% pasan, 50% se regeneran
 * - Garantiza calidad superior manteniendo costo computacional razonable
 */
public class ScoreValidatorJob {
    
    private static final Logger LOG = LoggerFactory.getLogger(ScoreValidatorJob.class);
    private static final double QUALITY_THRESHOLD = 0.85; // Umbral basado en mediana de distribución (7,887 respuestas)
    private static final int MAX_RETRIES = 3;

    public static void main(String[] args) throws Exception {
        // Configuración del entorno Flink
        final StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        
        String kafkaBroker = System.getenv().getOrDefault("KAFKA_BROKER", "kafka:9092");
        
        LOG.info("Iniciando Flink Score Validator Job");
        LOG.info("Kafka Broker: {}", kafkaBroker);

        // Source: Kafka Topic 'llm-responses-success'
        KafkaSource<String> source = KafkaSource.<String>builder()
                .setBootstrapServers(kafkaBroker)
                .setTopics("llm-responses-success")
                .setGroupId("flink-score-validator-group")
                .setStartingOffsets(OffsetsInitializer.latest())
                .setValueOnlyDeserializer(new SimpleStringSchema())
                .build();

        // Sink para preguntas que requieren regeneración
        KafkaSink<String> regenerateSink = KafkaSink.<String>builder()
                .setBootstrapServers(kafkaBroker)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic("questions-pending")
                        .setValueSerializationSchema(new SimpleStringSchema())
                        .build())
                .build();

        // Sink para respuestas validadas (alta calidad)
        KafkaSink<String> validatedSink = KafkaSink.<String>builder()
                .setBootstrapServers(kafkaBroker)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic("validated-responses")
                        .setValueSerializationSchema(new SimpleStringSchema())
                        .build())
                .build();

        // Stream principal
        DataStream<String> responses = env.fromSource(source, WatermarkStrategy.noWatermarks(), "Kafka Source");

        // Procesamiento: calcular score y decidir acción
        DataStream<ScoredResponse> scoredResponses = responses
                .process(new ScoreCalculator());

        // Split: respuestas de baja calidad van a regeneración
        scoredResponses
                .filter(sr -> sr.score < QUALITY_THRESHOLD && sr.retryCount < MAX_RETRIES)
                .map(sr -> {
                    ObjectMapper mapper = new ObjectMapper();
                    ObjectNode regenerateMsg = mapper.createObjectNode();
                    regenerateMsg.put("question_id", sr.questionId);
                    regenerateMsg.put("question_text", sr.questionText);
                    regenerateMsg.put("original_answer", sr.originalAnswer);
                    regenerateMsg.put("retry_count", sr.retryCount + 1);
                    regenerateMsg.put("reason", "low_quality_score");
                    regenerateMsg.put("previous_score", sr.score);
                    LOG.info("FLINK: Regenerando pregunta {} (score: {}, intento: {})", 
                             sr.questionId, sr.score, sr.retryCount + 1);
                    return mapper.writeValueAsString(regenerateMsg);
                })
                .sinkTo(regenerateSink);

        // Respuestas de alta calidad van a validación
        scoredResponses
                .filter(sr -> sr.score >= QUALITY_THRESHOLD || sr.retryCount >= MAX_RETRIES)
                .map(sr -> {
                    ObjectMapper mapper = new ObjectMapper();
                    ObjectNode validatedMsg = mapper.createObjectNode();
                    validatedMsg.put("question_id", sr.questionId);
                    validatedMsg.put("question_text", sr.questionText);
                    validatedMsg.put("answer_text", sr.answerText);
                    validatedMsg.put("original_answer", sr.originalAnswer);
                    validatedMsg.put("bert_score", sr.score);
                    validatedMsg.put("validation_status", sr.score >= QUALITY_THRESHOLD ? "approved" : "max_retries_reached");
                    validatedMsg.put("retry_count", sr.retryCount);
                    LOG.info("FLINK: Validando respuesta {} (score: {}, status: {})", 
                             sr.questionId, sr.score, validatedMsg.get("validation_status").asText());
                    return mapper.writeValueAsString(validatedMsg);
                })
                .sinkTo(validatedSink);

        // Ejecutar el job
        env.execute("Flink Score Validator Job");
    }

    /**
     * Función para calcular BERTScore de cada respuesta
     */
    public static class ScoreCalculator extends ProcessFunction<String, ScoredResponse> {
        
        private static final Logger LOG = LoggerFactory.getLogger(ScoreCalculator.class);
        private final ObjectMapper mapper = new ObjectMapper();
        
        @Override
        public void processElement(String value, Context ctx, Collector<ScoredResponse> out) {
            try {
                JsonNode json = mapper.readTree(value);
                
                String questionId = json.get("question_id").asText();
                String questionText = json.get("question_text").asText();
                String answerText = json.get("answer_text").asText();
                String originalAnswer = json.get("original_answer").asText();
                int retryCount = json.has("retry_count") ? json.get("retry_count").asInt() : 0;

                // Calcular BERTScore
                double score = calculateBertScore(questionText, answerText, originalAnswer);
                
                ScoredResponse result = new ScoredResponse();
                result.questionId = questionId;
                result.questionText = questionText;
                result.answerText = answerText;
                result.originalAnswer = originalAnswer;
                result.score = score;
                result.retryCount = retryCount;
                
                out.collect(result);
                
            } catch (Exception e) {
                LOG.error("Error procesando respuesta: {}", e.getMessage(), e);
            }
        }

        /**
         * Calcula BERTScore usando servicio externo (score_validator)
         * En producción, esto podría ser una API HTTP o cálculo local
         */
        private double calculateBertScore(String question, String answer, String reference) {
            try (CloseableHttpClient client = HttpClients.createDefault()) {
                HttpPost request = new HttpPost("http://score-validator:8000/calculate_score");
                
                ObjectNode payload = mapper.createObjectNode();
                payload.put("question", question);
                payload.put("answer", answer);
                payload.put("reference", reference);
                
                request.setEntity(new StringEntity(mapper.writeValueAsString(payload), StandardCharsets.UTF_8));
                request.setHeader("Content-Type", "application/json");
                
                try (CloseableHttpResponse response = client.execute(request)) {
                    BufferedReader reader = new BufferedReader(
                        new InputStreamReader(response.getEntity().getContent(), StandardCharsets.UTF_8));
                    StringBuilder result = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) {
                        result.append(line);
                    }
                    
                    JsonNode scoreResponse = mapper.readTree(result.toString());
                    return scoreResponse.get("bert_score").asDouble();
                }
                
            } catch (Exception e) {
                LOG.warn("Error calculando BERTScore, usando score por defecto: {}", e.getMessage());
                // Fallback: score neutro para no bloquear el pipeline
                return 0.5;
            }
        }
    }

    /**
     * Clase para almacenar respuesta con su score calculado
     */
    public static class ScoredResponse {
        public String questionId;
        public String questionText;
        public String answerText;
        public String originalAnswer;
        public double score;
        public int retryCount;
    }
}
