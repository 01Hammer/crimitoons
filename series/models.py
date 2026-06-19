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
    total_temporadas = models.IntegerField(blank=True, null=True)
    id_tmdb = models.IntegerField(unique=True, null=True, blank=True)

    def __str__(self):
        return self.titulo


class Season(models.Model):
    serie = models.ForeignKey(Serie, on_delete=models.CASCADE, related_name='seasons')
    season_number = models.IntegerField()
    total_episodes = models.IntegerField(default=0)

    class Meta:
        unique_together = ('serie', 'season_number')
        ordering = ['season_number']

    def __str__(self):
        return f"{self.serie.titulo} - T{self.season_number}"


class UserSeriesProgress(models.Model):
    class Status(models.TextChoices):
        WATCHING = 'watching', 'Viendo'
        COMPLETED = 'completed', 'Completada'
        PAUSED = 'paused', 'Pausada'
        DROPPED = 'dropped', 'Abandonada'

    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='series_progress')
    serie = models.ForeignKey(Serie, on_delete=models.CASCADE, related_name='user_progress')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WATCHING)
    score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    comment = models.TextField(blank=True, null=True, max_length=1000)
    current_season = models.IntegerField(default=1)
    current_episode = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('perfil', 'serie')
        verbose_name_plural = 'User series progress'

    def __str__(self):
        return f"{self.perfil.usuario.username} - {self.serie.titulo} ({self.status})"


class UserSeriesProgress(models.Model):
    class Status(models.TextChoices):
        PLAN_TO_WATCH = 'plan_to_watch', 'Por Ver'  # <-- Agregamos tu guardado rápido
        WATCHING = 'watching', 'Viendo'
        COMPLETED = 'completed', 'Completada'
        PAUSED = 'paused', 'Pausada'
        DROPPED = 'dropped', 'Abandonada'

    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='series_progress')
    serie = models.ForeignKey(Serie, on_delete=models.CASCADE, related_name='user_progress')
    
    # <-- Cambiamos el default a Status.PLAN_TO_WATCH
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLAN_TO_WATCH)
    
    score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    comment = models.TextField(blank=True, null=True, max_length=1000)
    current_season = models.IntegerField(default=1)
    current_episode = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('perfil', 'serie')
        verbose_name_plural = 'User series progress'

    def __str__(self):
        return f"{self.perfil.usuario.username} - {self.serie.titulo} ({self.get_status_display()})"

class CustomList(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='custom_lists')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('perfil', 'name')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.perfil.usuario.username} - {self.name}"


class CustomListEntry(models.Model):
    custom_list = models.ForeignKey(CustomList, on_delete=models.CASCADE, related_name='entries')
    serie = models.ForeignKey(Serie, on_delete=models.CASCADE, related_name='custom_list_entries')
    added_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('custom_list', 'serie')
        verbose_name_plural = 'Custom list entries'
        ordering = ['order', 'added_at']

    def __str__(self):
        return f"{self.custom_list.name} - {self.serie.titulo}"


class CustomEpisodeList(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='custom_episode_lists')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('perfil', 'name')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.perfil.usuario.username} - {self.name} (episodios)"


class CustomEpisodeListEntry(models.Model):
    custom_episode_list = models.ForeignKey(CustomEpisodeList, on_delete=models.CASCADE, related_name='entries')
    serie = models.ForeignKey(Serie, on_delete=models.CASCADE, related_name='custom_episode_list_entries')
    season_number = models.IntegerField()
    episode_number = models.IntegerField()
    episode_title = models.CharField(max_length=300, blank=True, null=True)
    added_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('custom_episode_list', 'serie', 'season_number', 'episode_number')
        verbose_name_plural = 'Custom episode list entries'
        ordering = ['order', 'added_at']

    def __str__(self):
        return f"{self.custom_episode_list.name} - {self.serie.titulo} S{self.season_number}E{self.episode_number}"