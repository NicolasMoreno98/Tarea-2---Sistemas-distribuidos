"""
Script simplificado para monitorear progreso del experimento de 1000 consultas
"""

import subprocess
import time
from datetime import datetime

def get_responses_count():
    """Obtiene el total de respuestas en PostgreSQL"""
    try:
        cmd = 'docker exec postgres_db psql -U user -d yahoo_db -t -c "SELECT COUNT(*) FROM responses;"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            return int(result.stdout.strip())
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 0

def main():
    print("="*80)
    print("MONITOREO EXPERIMENTO 1000 CONSULTAS - TAREA 2")
    print("="*80)
    
    initial_count = get_responses_count()
    target = initial_count + 1000
    
    print(f"\nRespuestas iniciales: {initial_count:,}")
    print(f"Meta: {target:,} respuestas")
    print(f"Faltan: 1,000 respuestas por procesar")
    print(f"\nIniciando monitoreo cada 30 segundos...")
    print("-"*80)
    
    start_time = time.time()
    last_count = initial_count
    iteration = 0
    
    try:
        while True:
            iteration += 1
            time.sleep(30)
            
            current_count = get_responses_count()
            new_responses = current_count - last_count
            total_processed = current_count - initial_count
            remaining = 1000 - total_processed
            elapsed = time.time() - start_time
            
            # Calcular velocidad
            rate = total_processed / (elapsed / 60) if elapsed > 0 else 0  # respuestas por minuto
            eta_minutes = remaining / rate if rate > 0 else 0
            
            progress_pct = (total_processed / 1000) * 100
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iteración {iteration}")
            print(f"  Total en DB: {current_count:,} (+{new_responses} en últimos 30s)")
            print(f"  Procesadas: {total_processed}/1,000 ({progress_pct:.1f}%)")
            print(f"  Faltan: {remaining:,}")
            print(f"  Velocidad: {rate:.1f} respuestas/min")
            print(f"  ETA: {eta_minutes:.1f} minutos")
            print(f"  Tiempo transcurrido: {elapsed/60:.1f} min")
            print("-"*80)
            
            last_count = current_count
            
            # Verificar si completó
            if total_processed >= 1000:
                print("\n" + "="*80)
                print("✅ EXPERIMENTO COMPLETADO!")
                print("="*80)
                print(f"Total procesado: {total_processed:,} respuestas")
                print(f"Tiempo total: {elapsed/60:.2f} minutos")
                print(f"Velocidad promedio: {rate:.2f} respuestas/min")
                break
                
    except KeyboardInterrupt:
        print("\n\n⚠️  Monitoreo detenido por el usuario")
        elapsed = time.time() - start_time
        total_processed = last_count - initial_count
        print(f"Procesadas hasta ahora: {total_processed:,}/1,000")
        print(f"Tiempo transcurrido: {elapsed/60:.2f} minutos")

if __name__ == "__main__":
    main()
