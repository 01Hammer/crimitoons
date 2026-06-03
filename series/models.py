from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    foto_perfil = models.ImageField(upload_to='fotos_perfil/', null=True, blank=True)
    banner = models.ImageField(upload_to='banners/', null=True, blank=True)
    bio = models.TextField(blank=True, null=True, max_length=500)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Perfil de {self.usuario.username}"

# Señal para crear automáticamente un Perfil cuando se crea un Usuario
@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)

@receiver(post_save, sender=User)
def guardar_perfil_usuario(sender, instance, **kwargs):
    instance.perfil.save()

class Serie(models.Model):
    titulo = models.CharField(max_length=200)
    sinopsis = models.TextField(blank=True, null=True)
    calificacion = models.FloatField(blank=True, null=True)
    poster_path = models.CharField(max_length=255, blank=True, null=True)
    backdrop_path = models.CharField(max_length=255, blank=True, null=True)
    fecha_estreno = models.CharField(max_length=20, blank=True, null=True)
    generos = models.CharField(max_length=255, blank=True, null=True)  # Para guardar "Animación, Acción"
    total_capitulos = models.IntegerField(blank=True, null=True)
    id_tmdb = models.IntegerField(unique=True, null=True, blank=True)

    def __str__(self):
        return self.titulo