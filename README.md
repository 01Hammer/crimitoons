🎬Crimitoons

**Una comunidad para quienes aman las series animadas.**
Descubre series, lleva el control de lo que ves, arma tus propias listas y conversa con otros fans.

> 🚧 **Proyecto en desarrollo.**
> Crimitoons se construye poco a poco y todavía no es una versión final. Algunas secciones pueden cambiar, verse incompletas o tener errores. ¡Gracias por tu paciencia y por pasarte por aquí!

---

## ✨ ¿Qué es Crimitoons?

Crimitoons nació como un catálogo para listar y organizar series animadas, y está creciendo hasta convertirse en un espacio social donde la gente puede compartir lo que piensa de sus series favoritas.

La idea es que sea un lugar acogedor y bonito de usar: nada corporativo, nada infantil, solo un rincón cómodo para hablar de animación.

> 📌 Por ahora el catálogo se centra en **series animadas occidentales**. El anime y las series de acción real quedan fuera.

## 🧩 ¿Qué se puede hacer?

**📺 Explorar series**
- Buscar series animadas y ver su ficha: sinopsis, géneros, calificación, temporadas y capítulos.
- Ver el detalle de cada serie en pestañas (ficha, episodios, estadísticas y comunidad).

**📚 Llevar tu biblioteca**
- Marcar cada serie como *Por ver*, *Viendo*, *Completada*, *Pausada* o *Abandonada*.
- Guardar en qué temporada y capítulo vas, ponerle una nota y dejar un comentario.
- Crear tus propias listas de series y listas de episodios.
- Guardar tus favoritas.

**👤 Tu perfil**
- Foto, banner y biografía.
- Un historial de actividad con lo que has ido viendo y opinando.

**💬 Comunidad**
- Un feed con las novedades de la gente.
- Publicaciones libres con texto, imágenes y video.
- Foros de debate por categoría: teorías, críticas, debates y noticias.
- Encuestas.
- Votos y comentarios en las publicaciones y en la actividad de otros usuarios.

## 🛠️ Hecho con

| Parte | Tecnología |
|---|---|
| Lenguaje y framework | Python + [Django](https://www.djangoproject.com/) |
| Base de datos | SQLite en local, PostgreSQL en producción |
| Interfaz | HTML, CSS y JavaScript |
| Información de series | [TMDB](https://www.themoviedb.org/) (The Movie Database) |
| Almacenamiento de imágenes y videos | [Supabase Storage](https://supabase.com/storage) |
| Servidor de producción | Gunicorn + WhiteNoise |

## 🚀 Probarlo en tu computador

Esta parte es para quienes quieran ejecutar el proyecto en su propia máquina. Necesitas tener [Python 3](https://www.python.org/downloads/) y [Git](https://git-scm.com/) instalados.

**1. Descarga el proyecto**

```bash
git clone https://github.com/01Hammer/crimitoons.git
cd crimitoons
```

**2. Crea un entorno virtual e instálalo todo**

```bash
python -m venv .venv

# En Windows:
.venv\Scripts\activate
# En macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

**3. Prepara la base de datos**

```bash
python manage.py migrate
```

Sin configurar nada más, el proyecto usa una base de datos SQLite local (`db.sqlite3`), así que no necesitas instalar un servidor de base de datos.

**4. (Opcional) Crea un usuario administrador**

```bash
python manage.py createsuperuser
```

**5. Enciende el servidor**

```bash
python manage.py runserver
```

Abre tu navegador en **http://127.0.0.1:8000/** y listo. 🎉

### 🔑 Servicios externos

Algunas funciones dependen de servicios externos que necesitan sus propias claves:

- **TMDB**: de aquí salen los datos de las series. Necesitas una [API key gratuita de TMDB](https://www.themoviedb.org/settings/api) para que la búsqueda y las fichas funcionen.
- **Supabase**: se usa para guardar las imágenes y videos que suben los usuarios. Si quieres probar la subida de archivos, define estas variables de entorno: `SUPABASE_URL` y `SUPABASE_KEY`.

Variables de entorno opcionales:

| Variable | Para qué sirve |
|---|---|
| `SECRET_KEY` | Clave secreta de Django (obligatoria en producción) |
| `DATABASE_URL` | Dirección de la base de datos (si no la defines, se usa SQLite) |
| `SUPABASE_URL` | Dirección de tu proyecto en Supabase |
| `SUPABASE_KEY` | Clave de acceso a Supabase Storage |

## 🗂️ Cómo está organizado

```
crimitoons/
├── config/          # Configuración general del proyecto Django
├── series/          # La aplicación principal
│   ├── models.py    # Series, perfiles, listas, publicaciones, votos...
│   ├── views.py     # La lógica de cada página
│   ├── urls.py      # Las direcciones del sitio
│   ├── templates/   # Las páginas HTML
│   └── static/      # Estilos CSS e imágenes
├── media/           # Archivos subidos (fotos, banners, publicaciones)
├── build.sh         # Pasos de construcción para el despliegue
├── manage.py        # Herramienta de comandos de Django
└── requirements.txt # Dependencias de Python
```

## 🗺️ Estado actual

Crimitoons está en **desarrollo activo**. Lo que se está trabajando ahora:

- Mejorar el diseño y la consistencia visual del feed de la comunidad.
- Ordenar y modularizar el código (estilos, scripts y vistas).
- Pulir el reproductor de video y la experiencia de publicar.

Si encuentras algo raro, es muy probable que ya esté en la lista de pendientes. 😉

## 💡 Sugerencias y errores

¿Se te ocurre una idea o encontraste un problema? Puedes abrir un [issue](https://github.com/01Hammer/crimitoons/issues) en este repositorio. Todo comentario es bienvenido.

## 🙏 Créditos

- Creado y mantenido por [@01Hammer](https://github.com/01Hammer).
- Los datos de las series provienen de [TMDB](https://www.themoviedb.org/). *Este producto usa la API de TMDB pero no está avalado ni certificado por TMDB.*
