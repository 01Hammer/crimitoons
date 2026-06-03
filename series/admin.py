from django.contrib import admin
from .models import Serie, Perfil

admin.site.register(Serie)

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'fecha_creacion', 'fecha_actualizacion')
    list_filter = ('fecha_creacion', 'fecha_actualizacion')
    search_fields = ('usuario__username', 'usuario__email')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')