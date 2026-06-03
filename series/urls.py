from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_invitado, name='index_invitado'),
    
    path('perfil/', views.perfil_usuario, name='perfil_usuario'),
    path('nueva/', views.crear_serie, name='crear_serie'),
    path('eliminar/<int:serie_id>/', views.eliminar_serie, name='eliminar_serie'),
    path('buscar/', views.buscar_series, name='buscar_series'),
    path('serie/<int:serie_id>/', views.detalle_serie, name='detalle_serie'),
    
    # URLs de autenticación
    path('registro/', views.registro, name='registro'),
    path('login/', views.iniciar_sesion, name='iniciar_sesion'),
    path('logout/', views.cerrar_sesion, name='cerrar_sesion'),
    path('editar-perfil/', views.editar_perfil, name='editar_perfil'),
    path('perfil/<str:username>/', views.ver_perfil, name='ver_perfil'),
]