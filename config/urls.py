from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
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
