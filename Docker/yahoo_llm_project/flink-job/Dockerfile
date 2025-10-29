# Dockerfile para compilar y desplegar el Flink job

FROM maven:3.9-eclipse-temurin-11 AS builder

WORKDIR /app

# Copiar POM y descargar dependencias
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Copiar código fuente y compilar
COPY src ./src
RUN mvn clean package -DskipTests

# Imagen final
FROM flink:1.18-scala_2.12

# Copiar JAR compilado
COPY --from=builder /app/target/flink-score-validator-1.0.jar /opt/flink/usrlib/

# El job se desplegará manualmente o mediante script
