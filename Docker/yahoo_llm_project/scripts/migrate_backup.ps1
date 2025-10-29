# Script PowerShell para migrar backup de Tarea 1 a Tarea 2
Write-Host "Iniciando migracion de backup..." -ForegroundColor Cyan

$inputFile = "..\dataset\backup_responses.sql"
$outputFile = "..\dataset\backup_tarea2.sql"

# Contador
$processed = 0
$errors = 0

# Crear archivo de salida
$output = @()
$output += "-- Backup migrado a esquema Tarea 2"
$output += "-- Fecha: $(Get-Date)"
$output += "SET client_encoding = 'UTF8';"
$output += ""

# Leer archivo línea por línea
Get-Content $inputFile -Encoding UTF8 | ForEach-Object {
    $line = $_
    
    # Solo procesar líneas INSERT
    if ($line -match "^INSERT INTO public\.responses") {
        try {
            # Extraer valores entre VALUES ( ... );
            if ($line -match "VALUES \((.*)\);") {
                $values = $matches[1]
                
                # Split básico por comas (no perfecto pero funcional)
                # Formato: id, question, human_answer, llm_answer, score, count, created_at, updated_at
                
                # Extraer campos usando regex
                if ($values -match "^'([^']+)',\s*'([^']+)',\s*'(.*?)',\s*'(.*?)',\s*([\d.]+),\s*(\d+),\s*'([^']+)',\s*'([^']+)'") {
                    $id = $matches[1]
                    $question = $matches[2]
                    $human_ans = $matches[3]
                    $llm_ans = $matches[4]
                    $score = $matches[5]
                    $count = $matches[6]
                    $created = $matches[7]
                    $updated = $matches[8]
                    
                    # Generar question_id (16 caracteres)
                    $hash = [System.Security.Cryptography.MD5]::Create()
                    $bytes = [System.Text.Encoding]::UTF8.GetBytes("$id$question")
                    $hashBytes = $hash.ComputeHash($bytes)
                    $qid = [System.BitConverter]::ToString($hashBytes).Replace("-","").Substring(0,16).ToLower()
                    
                    # Calcular processing_time
                    $procTime = 500 * [int]$count
                    
                    # Escapar comillas simples
                    $question = $question.Replace("'", "''")
                    $human_ans = $human_ans.Replace("'", "''")
                    $llm_ans = $llm_ans.Replace("'", "''")
                    
                    # Construir nuevo INSERT
                    $newLine = "INSERT INTO public.responses (question_id, question_text, llm_response, original_answer, bert_score, processing_attempts, total_processing_time_ms, created_at, updated_at) VALUES ('$qid', '$question', '$llm_ans', '$human_ans', $score, $count, $procTime, '$created', '$updated');"
                    
                    $output += $newLine
                    $processed++
                    
                    if ($processed % 1000 -eq 0) {
                        Write-Host "Procesados: $processed" -ForegroundColor Green
                    }
                }
            }
        }
        catch {
            $errors++
            if ($errors -lt 10) {
                Write-Host "Error: $_" -ForegroundColor Red
            }
        }
    }
}

# Escribir archivo
$output | Out-File -FilePath $outputFile -Encoding UTF8

Write-Host "`nMigracion completada!" -ForegroundColor Green
Write-Host "Registros migrados: $processed" -ForegroundColor Cyan
Write-Host "Errores: $errors" -ForegroundColor Yellow
Write-Host "Archivo: $outputFile" -ForegroundColor Cyan
