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
    # Lee los datos ocultos que guardaste en el paso 1
    admin_user = os.getenv('DJANGO_SUPERUSER_USERNAME')
    admin_pass = os.getenv('DJANGO_SUPERUSER_PASSWORD')

    # Solo se ejecuta si configuraste las variables en Render
    if admin_user and admin_pass:
        if not User.objects.filter(username=admin_user).exists():
            User.objects.create_superuser(admin_user, 'hammer@correo.com', admin_pass)
            print(f"¡Usuario {admin_user} asegurado correctamente!")
except Exception as e:
    print(f"Error en script de superusuario: {e}")
# ----------------------------------------------------
