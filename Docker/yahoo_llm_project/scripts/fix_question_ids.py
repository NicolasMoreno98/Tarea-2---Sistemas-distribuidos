import psycopg2
import hashlib
import sys

# Configuración de conexión (para Docker)
import os
DATABASE_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'postgres_db'),
    'port': 5432,
    'database': 'yahoo_db',
    'user': 'user',
    'password': 'password'
}

def generate_question_id(question_text):
    """Generar ID único basado en hash del texto (mismo método que storage_service)"""
    return hashlib.sha256(question_text.encode('utf-8')).hexdigest()[:16]

def fix_question_ids():
    """Actualizar question_id y eliminar duplicados"""
    
    try:
        # Conectar a PostgreSQL
        conn = psycopg2.connect(**DATABASE_CONFIG)
        conn.autocommit = False
        cursor = conn.cursor()
        print("✓ Conectado a PostgreSQL")
        
        # 1. Ver estadísticas ANTES
        print("\n" + "="*60)
        print("📊 ESTADÍSTICAS ANTES DEL CAMBIO")
        print("="*60)
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT question_text) as textos_unicos,
                COUNT(DISTINCT question_id) as ids_unicos
            FROM responses
        """)
        total, textos_unicos, ids_unicos = cursor.fetchone()
        duplicados = total - textos_unicos
        
        print(f"Total de registros:     {total:,}")
        print(f"Textos únicos:          {textos_unicos:,}")
        print(f"IDs únicos:             {ids_unicos:,}")
        print(f"Duplicados (texto):     {duplicados:,}")
        
        # 2. Obtener todas las preguntas y calcular nuevos IDs
        print("\n" + "="*60)
        print("🔄 PROCESANDO PREGUNTAS...")
        print("="*60)
        
        cursor.execute("""
            SELECT question_id, question_text, created_at
            FROM responses
            ORDER BY question_text, created_at DESC
        """)
        
        all_responses = cursor.fetchall()
        print(f"✓ Leídas {len(all_responses):,} preguntas")
        
        # 3. Agrupar por texto y mantener solo la más reciente
        text_to_latest = {}
        for old_id, text, created_at in all_responses:
            new_id = generate_question_id(text)
            
            if text not in text_to_latest:
                text_to_latest[text] = {
                    'old_id': old_id,
                    'new_id': new_id,
                    'created_at': created_at
                }
            # Si este registro es más reciente, actualizar
            elif created_at > text_to_latest[text]['created_at']:
                text_to_latest[text] = {
                    'old_id': old_id,
                    'new_id': new_id,
                    'created_at': created_at
                }
        
        ids_to_keep = {info['old_id'] for info in text_to_latest.values()}
        ids_to_delete = [old_id for old_id, _, _ in all_responses if old_id not in ids_to_keep]
        
        print(f"✓ Registros a mantener: {len(ids_to_keep):,}")
        print(f"✗ Registros a eliminar: {len(ids_to_delete):,}")
        
        # 4. Eliminar duplicados
        if ids_to_delete:
            print(f"\n🗑️  Eliminando {len(ids_to_delete):,} duplicados...")
            cursor.execute("""
                DELETE FROM responses
                WHERE question_id = ANY(%s)
            """, (ids_to_delete,))
            print(f"✓ Eliminados {cursor.rowcount:,} registros")
        
        # 5. Actualizar question_id con el nuevo hash
        print("\n🔧 Actualizando question_id...")
        updates = [(info['new_id'], info['old_id']) for info in text_to_latest.values()]
        
        cursor.executemany("""
            UPDATE responses
            SET question_id = %s
            WHERE question_id = %s
        """, updates)
        print(f"✓ Actualizados {cursor.rowcount:,} registros")
        
        # 6. Ver estadísticas DESPUÉS
        print("\n" + "="*60)
        print("📊 ESTADÍSTICAS DESPUÉS DEL CAMBIO")
        print("="*60)
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT question_text) as textos_unicos,
                COUNT(DISTINCT question_id) as ids_unicos
            FROM responses
        """)
        total, textos_unicos, ids_unicos = cursor.fetchone()
        
        print(f"Total de registros:     {total:,}")
        print(f"Textos únicos:          {textos_unicos:,}")
        print(f"IDs únicos:             {ids_unicos:,}")
        
        # Verificar integridad
        if total == textos_unicos == ids_unicos:
            print("✅ VERIFICACIÓN: Todos los registros son únicos")
        else:
            print("⚠️  ADVERTENCIA: Aún hay inconsistencias")
            conn.rollback()
            return False
        
        # 7. Mostrar ejemplos
        print("\n" + "="*60)
        print("📋 EJEMPLOS DE REGISTROS ACTUALIZADOS")
        print("="*60)
        
        cursor.execute("""
            SELECT question_id, LEFT(question_text, 60) as texto_corto, bert_score
            FROM responses
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        for qid, texto, score in cursor.fetchall():
            print(f"ID: {qid} | Score: {score:.4f} | {texto}...")
        
        # 8. Commit
        print("\n💾 Guardando cambios...")
        conn.commit()
        print("✅ Cambios guardados exitosamente")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    print("="*60)
    print("  FIX QUESTION_ID - Actualizar y Eliminar Duplicados")
    print("="*60)
    print("\nEste script:")
    print("1. Recalculará question_id usando hash(question_text)")
    print("2. Eliminará duplicados (mantendrá el más reciente)")
    print("3. Actualizará todos los registros")
    print("\n⚠️  AUTO-EJECUTANDO (sin confirmación)")
    
    success = fix_question_ids()
    sys.exit(0 if success else 1)
