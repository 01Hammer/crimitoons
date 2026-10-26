import os
import uuid
import requests

def subir_a_supabase(archivo, folder="general"):
    """
    Sube un archivo recibido desde un formulario de Django directamente 
    al Storage de Supabase y retorna la URL pública permanente.
    """
    if not archivo:
        return None

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    bucket_name = "media"  # El nombre del bucket público en Supabase

    if not supabase_url or not supabase_key:
        raise ValueError("Las credenciales de Supabase no están configuradas en las variables de entorno.")

    # Extraemos la extensión original del archivo (ej: .jpg, .png)
    ext = os.path.splitext(archivo.name)[1]
    
    # Generamos un nombre único usando UUID para evitar conflictos de duplicados (409)
    nombre_unico = f"{uuid.uuid4().hex}{ext}"
    nombre_archivo = f"{folder}/{nombre_unico}"
    
    # Endpoint de Supabase Storage para subir objetos
    url = f"{supabase_url}/storage/v1/object/{bucket_name}/{nombre_archivo}"

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": getattr(archivo, 'content_type', 'application/octet-stream')
    }

    # Leemos los datos binarios del archivo subido en Django
    response = requests.post(url, data=archivo.read(), headers=headers)

    if response.status_code in [200, 201]:
        # Construimos y retornamos la URL pública definitiva de la imagen
        public_url = f"{supabase_url}/storage/v1/object/public/{bucket_name}/{nombre_archivo}"
        return public_url
    else:
        raise Exception(f"Error al subir la imagen a Supabase: {response.text}")
