import os
import pandas as pd
from pytrends.request import TrendReq
import time
from dotenv import load_dotenv
from supabase import create_client, Client

# 1. Cargar configuración y conectar a Supabase
load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Error: Faltan credenciales de Supabase en el archivo .env")
    exit(1)

supabase: Client = create_client(url, key)

# 2. Conectar a Google Trends
pytrends = TrendReq(hl='es-MX', tz=360)

marcas = ["Nike", "Adidas", "Puma", "Vans", "Charly"]
categorias = ["tenis para correr", "ropa de gimnasio"]

# Diccionario con los códigos de los estados de México (ISO 3166-2)
estados_mx = {
    'MX-AGU': 'Aguascalientes', 'MX-BCN': 'Baja California', 'MX-BCS': 'Baja California Sur',
    'MX-CAM': 'Campeche', 'MX-COA': 'Coahuila', 'MX-COL': 'Colima', 'MX-CHP': 'Chiapas',
    'MX-CHH': 'Chihuahua', 'MX-CMX': 'Ciudad de México', 'MX-DUR': 'Durango',
    'MX-GUA': 'Guanajuato', 'MX-GRO': 'Guerrero', 'MX-HID': 'Hidalgo', 'MX-JAL': 'Jalisco',
    'MX-MEX': 'Estado de México', 'MX-MIC': 'Michoacán', 'MX-MOR': 'Morelos',
    'MX-NAY': 'Nayarit', 'MX-NLE': 'Nuevo León', 'MX-OAX': 'Oaxaca', 'MX-PUE': 'Puebla',
    'MX-QUE': 'Querétaro', 'MX-ROO': 'Quintana Roo', 'MX-SLP': 'San Luis Potosí',
    'MX-SIN': 'Sinaloa', 'MX-SON': 'Sonora', 'MX-TAB': 'Tabasco', 'MX-TAM': 'Tamaulipas',
    'MX-TLA': 'Tlaxcala', 'MX-VER': 'Veracruz', 'MX-YUC': 'Yucatán', 'MX-ZAC': 'Zacatecas'
}

datos_totales = []

print("Iniciando la extracción estado por estado. Esto tomará varios minutos...")

for codigo_estado, nombre_estado in estados_mx.items():
    print(f"Consultando datos para: {nombre_estado}...")
    
    try:
        # --- Consulta de Marcas ---
        pytrends.build_payload(marcas, cat=0, timeframe='today 12-m', geo=codigo_estado)
        df_marcas = pytrends.interest_over_time().reset_index()
        if 'isPartial' in df_marcas.columns:
            df_marcas = df_marcas.drop(columns=['isPartial'])
            
        time.sleep(6)

        # --- Consulta de Categorías ---
        pytrends.build_payload(categorias, cat=0, timeframe='today 12-m', geo=codigo_estado)
        df_categorias = pytrends.interest_over_time().reset_index()
        if 'isPartial' in df_categorias.columns:
            df_categorias = df_categorias.drop(columns=['isPartial'])
            
        time.sleep(6)
        
        # Unir marcas y categorías
        if not df_marcas.empty and not df_categorias.empty:
            df_estado = pd.merge(df_marcas, df_categorias, on='date', how='outer')
            
            # Identificadores geográficos
            df_estado['estado'] = nombre_estado
            df_estado['codigo_iso'] = codigo_estado
            
            datos_totales.append(df_estado)
        else:
            print(f"  -> No se encontraron suficientes datos para {nombre_estado}")

    except Exception as e:
        print(f"  -> Error al consultar {nombre_estado}: {e}")
        time.sleep(20) 

# 3. Consolidar, limpiar y enviar a Supabase
if datos_totales:
    df_consolidado = pd.concat(datos_totales, ignore_index=True)
    
    # Renombrar columnas a snake_case para PostgreSQL
    nuevos_nombres = {
        'tenis para correr': 'tenis_para_correr',
        'ropa de gimnasio': 'ropa_de_gimnasio',
        'date': 'fecha'
    }
    df_consolidado.rename(columns=nuevos_nombres, inplace=True)
    df_consolidado.columns = df_consolidado.columns.str.lower()
    
    # Convertir la fecha a formato string (YYYY-MM-DD) para evitar errores de JSON en Supabase
    df_consolidado['fecha'] = pd.to_datetime(df_consolidado['fecha']).dt.strftime('%Y-%m-%d')

    columnas_deseadas = ['estado', 'codigo_iso', 'fecha', 'nike', 'adidas', 'puma', 'vans', 'charly', 'tenis_para_correr', 'ropa_de_gimnasio']
    columnas_finales = [col for col in columnas_deseadas if col in df_consolidado.columns]
    df_consolidado = df_consolidado[columnas_finales]
    
    # Llenar posibles valores nulos con 0 (PostgreSQL rechaza NaN en columnas enteras)
    df_consolidado = df_consolidado.fillna(0)

    df_consolidado = df_consolidado.sort_values(by=['estado', 'fecha'])
    
    # Convertir el DataFrame de Pandas a una lista de diccionarios
    datos_trends = df_consolidado.to_dict(orient='records')
    
    print(f"\nSe procesaron {len(datos_trends)} registros. Enviando a Supabase...")
    
    try:
        # Usamos upsert para actualizar datos existentes o insertar nuevos
        respuesta = supabase.table('tendencias_trends').upsert(datos_trends).execute()
        print("¡Datos guardados exitosamente en la tabla 'tendencias_trends'!")
    except Exception as e:
        print(f"Error al guardar en Supabase: {e}")
        
else:
    print("\nNo se pudieron extraer datos.")