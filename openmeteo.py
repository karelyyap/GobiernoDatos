import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Coordenadas de Mazatlán
LATITUD = 23.2329
LONGITUD = -106.4062
CODIGO_ISO = "MX-SIN"
ESTADO = "Sinaloa"

# 1. Cargar configuración y conectar a Supabase
load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Error: Faltan credenciales de Supabase en el archivo .env")
    exit(1)

supabase: Client = create_client(url, key)

def obtener_y_procesar_clima():
    print("Consultando datos en Open-Meteo...")
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUD}&longitude={LONGITUD}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&past_days=30&forecast_days=14&timezone=auto"
    
    respuesta = requests.get(url)
    if respuesta.status_code != 200:
        print(f"Error de conexión: {respuesta.status_code}")
        return []
        
    datos = respuesta.json()['daily']
    hoy = datetime.now().strftime("%Y-%m-%d")
    datos_procesados = []
    
    for f, t_max, t_min, p in zip(datos['time'], datos['temperature_2m_max'], datos['temperature_2m_min'], datos['precipitation_sum']):
        t_max = t_max if t_max is not None else 0
        t_min = t_min if t_min is not None else 0
        p = p if p is not None else 0
        
        if f < hoy:
            periodo = "histórico"
        elif f == hoy:
            periodo = "actual"
        else:
            periodo = "pronóstico"
            
        impacto = "normal"
        if p >= 15:
            impacto = "lluvias fuertes (calzado)"
        elif t_max >= 32.0:
            impacto = "ola de calor (ropa ligera)"
            
        datos_procesados.append({
            "codigo_iso": CODIGO_ISO,
            "estado": ESTADO,
            "fecha": f,
            "periodo": periodo,
            "temp_max": t_max,
            "temp_min": t_min,
            "lluvia_mm": p,
            "impacto": impacto
        })
        
    return datos_procesados

def main():
    datos = obtener_y_procesar_clima()
    
    if not datos:
        print("No hay datos para procesar.")
        return
        
    print(f"Se procesaron {len(datos)} registros de clima.")
    print("Enviando datos a Supabase...")
    
    try:
        # El método upsert inserta nuevos o actualiza los existentes basado en (codigo_iso, fecha)
        respuesta = supabase.table('clima_diario').upsert(datos, on_conflict='codigo_iso,fecha').execute()
        print("¡Datos guardados exitosamente en la tabla 'clima_diario'!")
    except Exception as e:
        print(f"Error al guardar en Supabase: {e}")

if __name__ == "__main__":
    main()
