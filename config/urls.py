import os
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import get_user_model
from series import views  # <--- CORREGIDO: Importa desde la app 'series'

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Le decimos al proyecto que use las rutas internas de nuestra app
    path('', include('series.urls')),
]

# Configuración para entorno de desarrollo (DEBUG = True)
if settings.DEBUG:
    # Servir TODOS los archivos de media (imágenes, gifs y videos) con soporte
    # de Range Requests. Se eliminó el static() estándar porque, al estar
    # registrado antes, capturaba las peticiones primero e impedía que esta
    # vista con soporte de Range llegara a ejecutarse.
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', views.servir_media_con_rango),
    ]

try:
    User = get_user_model()
    # Si 'hammer' no existe, lo crea. Si existe, le actualiza la contraseña para asegurar el acceso.
    usuario, creado = User.objects.get_or_create(
        username='hammer',
        defaults={'email': 'hammer@correo.com', 'is_staff': True, 'is_superuser': True}
    )
    usuario.set_password('hammer123')
    usuario.save()
    print("¡Usuario 'hammer' configurado y actualizado con éxito!")
except Exception as e:
    print(f"Error forzando el superusuario: {e}")
# --------------------------------------

# --- SCRIPT AUTOMÁTICO DE MIGRACIONES COMPLETO ---
from django.core.management import call_command
from django.contrib.auth import get_user_model

try:
    # 1. Detectar cambios en los modelos (como el ImageField) y crear los archivos de migración
    print("--- GENERANDO ARCHIVOS DE MIGRACIÓN PARA POSTGRESQL ---")
    call_command('makemigrations', 'series', interactive=False)
    
    # 2. Aplicar los cambios directamente en la base de datos de Render
    print("--- EJECUTANDO MIGRACIONES EN LA BASE DE DATOS ---")
    call_command('migrate', interactive=False)
    print("--- BASE DE DATOS ACTUALIZADA CON ÉXITO ---")

    # 3. Asegurar tu cuenta de administrador
    User = get_user_model()
    usuario, creado = User.objects.get_or_create(
        username='hammer',
        defaults={'email': 'hammer@correo.com', 'is_staff': True, 'is_superuser': True}
    )
    usuario.set_password('hammer123')
    usuario.save()
    print("--- USUARIO 'hammer' VERIFICADO Y OPERATIVO ---")

except Exception as e:
    print(f"--- ERROR EN EL ARRANQUE DEL SCRIPT AUTOMÁTICO: {e} ---")
# --------------------------------------------------
