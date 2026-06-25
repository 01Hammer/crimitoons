import datetime
import requests
import json
import random

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from .models import Serie, Perfil, UserSeriesProgress, HistorialActividad, VotoActividad, ComentarioActividad, ComunidadPost
from .forms import RegistroForm, LoginForm, ActualizarPerfilForm
from django.http import JsonResponse, Http404
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.utils.timesince import timesince
from django.utils import timezone
from django.db.models import Count  # <-- Asegúrate de que esta línea esté presente

DEFAULT_POSTER = "https://placehold.co/500x750/3D262B/F7F3E3?text=No+Poster"
API_KEY_TMDB = "ea735303fe1aa8a04e298b1f9c130e6c"
IDIOMAS_BLOQUEADOS = {"ja", "zh", "ko", "cn"}
PALABRAS_PROHIBIDAS = [
    "hentai", "ecchi", "yaoi", "yuri", "shota", "loli", 
    "adult animation", "erotic", "erótica", "nude", "nudity"
]
MAPA_PAISES = {
    "US": "Estados Unidos", "CA": "Canadá", "JP": "Japón", 
    "FR": "Francia", "KR": "Corea del Sur", "GB": "Reino Unido", 
    "ES": "España", "MX": "México", "CO": "Colombia", "BR": "Brasil"
}
MAPA_NOMBRES_ACTORES = {
    "mum": "Johanna",
    "wood man": "Hombre de Madera",
    "the librarian": "Kaisa (Bibliotecaria)",
    "librarian": "Kaisa (Bibliotecaria)",
}

# ============================================================
# HELPERS / UTILIDADES DE EXTRACCIÓN Y LIMPIEZA (BACKEND)
# ============================================================

def obtener_generos_tmdb(api_key):
    url = f"https://api.themoviedb.org/3/genre/tv/list?api_key={api_key}&language=en-US"
    try:
        res = requests.get(url, timeout=2.0).json()
        return {g["id"]: g["name"] for g in res.get("genres", [])}
    except Exception:
        return {}


def verificar_pelicula_animada(movie_id):
    try:
        url_movie = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY_TMDB}&language=en-US"
        res_movie = requests.get(url_movie, timeout=3.0)
        if res_movie.status_code != 200:
            return False
        datos_movie = res_movie.json()

        ids_genero_movie = [g["id"] for g in datos_movie.get("genres", [])]
        if 16 not in ids_genero_movie:
            return False

        if datos_movie.get("original_language", "") in IDIOMAS_BLOQUEADOS:
            return False

        titulo_movie = datos_movie.get("original_title") or datos_movie.get("title", "")
        if not titulo_movie:
            return False

        url_busq = f"https://api.themoviedb.org/3/search/tv?api_key={API_KEY_TMDB}&language=en-US&query={titulo_movie}"
        res_busq = requests.get(url_busq, timeout=3.0)
        if res_busq.status_code == 200:
            for resultado in res_busq.json().get("results", []):
                if 16 in resultado.get("genre_ids", []):
                    if resultado.get("original_language", "") not in IDIOMAS_BLOQUEADOS:
                        return True
    except Exception:
        pass
    return False


def limpiar_nombre_personaje(personaje_sucio):
    limpio = (personaje_sucio or "").replace(" (voice)", "").split(" / ")[0].strip()
    if not limpio:
        return "Sin especificar"
    return MAPA_NOMBRES_ACTORES.get(limpio.lower(), limpio)


def procesar_creditos_api(tmdb_id, num_temporada):
    diccionario_actores = {}
    diccionario_staff = {}

    def _actor(persona, char_name=None):
        uid = persona.get("id")
        if not uid: return
        p_limpio = limpiar_nombre_personaje(char_name or persona.get("character") or "")
        if uid not in diccionario_actores:
            diccionario_actores[uid] = {
                "nombre": persona.get("name"),
                "personaje": p_limpio,
                "foto_path": persona.get("profile_path"),
            }
        elif p_limpio not in diccionario_actores[uid]["personaje"]:
            diccionario_actores[uid]["personaje"] += f", {p_limpio}"

    def _staff(persona, job_name=None):
        uid = persona.get("id")
        if not uid: return
        rol = job_name or persona.get("job") or persona.get("department") or "Sin especificar"
        if uid not in diccionario_staff:
            diccionario_staff[uid] = {
                "nombre": persona.get("name"),
                "roles_lista": [rol],
                "foto_path": persona.get("profile_path"),
            }
        elif rol not in diccionario_staff[uid]["roles_lista"]:
            diccionario_staff[uid]["roles_lista"].append(rol)

    url_aggregate = f"https://api.themoviedb.org/3/tv/{tmdb_id}/aggregate_credits?api_key={API_KEY_TMDB}&language=es-MX"
    creditos_ok = False
    try:
        res = requests.get(url_aggregate, timeout=4.0)
        if res.status_code == 200:
            datos = res.json()
            for p in datos.get("cast", []):
                roles = p.get("roles") or []
                if not roles: _actor(p, "")
                for r in roles: _actor(p, r.get("character"))
            for p in datos.get("crew", []):
                jobs = p.get("jobs") or []
                if not jobs: _staff(p, p.get("known_for_department") or p.get("department"))
                for j in jobs: _staff(p, j.get("job"))
            creditos_ok = bool(diccionario_actores or diccionario_staff)
    except Exception:
        pass

    if not creditos_ok:
        url_season = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{num_temporada}/credits?api_key={API_KEY_TMDB}&language=es-MX"
        try:
            res = requests.get(url_season, timeout=4.0)
            if res.status_code == 200:
                datos = res.json()
                for c in datos.get("cast", []): _actor(c)
                for cr in datos.get("crew", []): _staff(cr)
        except Exception:
            pass

    actores = sorted(diccionario_actores.values(), key=lambda a: (a["nombre"] or "").lower())
    staff = sorted(diccionario_staff.values(), key=lambda m: (m["nombre"] or "").lower())
    return actores, staff


def inferir_detalles_produccion(datos_gen):
    detalles = {
        "estudio": "No disponible",
        "pais": "No disponible",
        "tecnica": "Animación 2D",
        "publico": "Para todos los públicos (G)",
    }
    if not datos_gen:
        return detalles

    networks = datos_gen.get("networks", [])
    if networks:
        detalles["estudio"] = networks[0].get("name")

    paises_origen = datos_gen.get("origin_country", [])
    paises_produccion = datos_gen.get("production_countries", [])
    codigo_pais = paises_origen[0] if paises_origen else (paises_produccion[0].get("iso_3166_1") if paises_produccion else None)
    if codigo_pais:
        detalles["pais"] = MAPA_PAISES.get(str(codigo_pais).upper().strip(), codigo_pais)

    ratings = datos_gen.get("content_ratings", {}).get("results", [])
    for r in ratings:
        if r.get("iso_3166_1") in ["US", "MX"]:
            rating_code = r.get("rating")
            if rating_code in ["TV-Y", "TV-G", "G"]: detalles["publico"] = "Apto para todo público"
            elif rating_code in ["TV-Y7", "TV-Y7-FV", "PG"]: detalles["publico"] = "Infantil / Juvenil (7+)"
            elif rating_code in ["TV-PG", "TV-14", "PG-13"]: detalles["publico"] = "Adolescentes (14+)"
            elif rating_code in ["TV-MA", "R"]: detalles["publico"] = "Animación Adulta (18+)"
            break
    return detalles


# ============================================================
# 1. VISTAS DE CONTENIDO (DETALLE Y PROGRESO)
# ============================================================

def detalle_serie(request, serie_id):
    serie = Serie.objects.filter(id_tmdb=serie_id).first() or Serie.objects.filter(id=serie_id).first()

    if serie is None:
        url_creacion = f"https://api.themoviedb.org/3/tv/{serie_id}?api_key={API_KEY_TMDB}&language=en-US"
        try:
            res = requests.get(url_creacion, timeout=3.0)
            if res.status_code == 200:
                datos = res.json()
                if datos.get("original_language", "") in IDIOMAS_BLOQUEADOS or 16 not in [g["id"] for g in datos.get("genres", [])]:
                    raise Http404("Este contenido no está disponible en este catálogo.")

                poster_raw = datos.get("poster_path")
                backdrop_raw = datos.get("backdrop_path")
                serie = Serie.objects.create(
                    id_tmdb=serie_id,
                    titulo=datos.get("original_name") or datos.get("name"),
                    sinopsis=datos.get("overview") or "Sin sinopsis disponible.",
                    poster_path="https://image.tmdb.org/t/p/w500" + poster_raw if poster_raw else None,
                    backdrop_path="https://image.tmdb.org/t/p/original" + backdrop_raw if backdrop_raw else None,
                    total_capitulos=datos.get("number_of_episodes", 0),
                )
            elif verificar_pelicula_animada(serie_id):
                url_movie = f"https://api.themoviedb.org/3/movie/{serie_id}?api_key={API_KEY_TMDB}&language=es-MX"
                res_movie = requests.get(url_movie, timeout=3.0)
                if res_movie.status_code == 200:
                    datos_m = res_movie.json()
                    poster_raw = datos_m.get("poster_path")
                    backdrop_raw = datos_m.get("backdrop_path")
                    serie = Serie.objects.create(
                        id_tmdb=serie_id,
                        titulo=datos_m.get("original_title") or datos_m.get("title"),
                        sinopsis=datos_m.get("overview") or "Sin sinopsis disponible.",
                        poster_path="https://image.tmdb.org/t/p/w500" + poster_raw if poster_raw else None,
                        backdrop_path="https://image.tmdb.org/t/p/original" + backdrop_raw if backdrop_raw else None,
                        total_capitulos=1,
                    )
                else:
                    raise Http404("La película no existe en ninguna plataforma")
            else:
                raise Http404("Este contenido no está disponible en este catálogo.")
        except Http404: raise
        except Exception: raise Http404("Error al conectar con el servicio externo.")

    num_temporada = int(request.GET.get("temporada", 1))
    tmdb_id = getattr(serie, "id_tmdb", None)

    progreso_usuario = None
    if request.user.is_authenticated:
        progreso_usuario = UserSeriesProgress.objects.filter(perfil=request.user.perfil, serie=serie).first()

    if not tmdb_id:
        try:
            url_busq = f"https://api.themoviedb.org/3/search/tv?api_key={API_KEY_TMDB}&query={serie.titulo}&language=es-MX"
            res_b = requests.get(url_busq, timeout=3.0).json()
            if res_b.get("results"): tmdb_id = res_b["results"][0].get("id")
        except Exception: pass

    total_temporadas = 1
    generos_principales = []
    datos_gen = {}

    url_general = f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={API_KEY_TMDB}&language=es-MX&append_to_response=content_ratings"
    try:
        response_gen = requests.get(url_general, timeout=3.0)
        if response_gen.status_code == 200:
            datos_gen = response_gen.json()
            total_temporadas = datos_gen.get("number_of_seasons", 1)
            generos_principales = [g.get("name", "") for g in datos_gen.get("genres", []) if g.get("name")]
            serie.calificacion = datos_gen.get("vote_average") or serie.calificacion
            serie.total_capitulos = datos_gen.get("number_of_episodes") or serie.total_capitulos
            serie.fecha_estreno = datos_gen.get("first_air_date") or serie.fecha_estreno
            serie.sinopsis = datos_gen.get("overview") or serie.sinopsis
            if datos_gen.get("poster_path"): serie.poster_path = "https://image.tmdb.org/t/p/w500" + datos_gen["poster_path"]
            if datos_gen.get("backdrop_path"): serie.backdrop_path = "https://image.tmdb.org/t/p/original" + datos_gen["backdrop_path"]
    except Exception: pass

    url_ingles = f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={API_KEY_TMDB}&language=en-US"
    try:
        response_en = requests.get(url_ingles, timeout=3.0)
        if response_en.status_code == 200:
            datos_en = response_en.json()
            if datos_en.get("original_name") or datos_en.get("name"):
                serie.titulo = datos_en.get("original_name") or datos_en.get("name")
    except Exception: pass

    if not serie.poster_path: serie.poster_path = DEFAULT_POSTER
    serie.total_temporadas = total_temporadas
    
    # Se limita estrictamente a los 3 primeros generos para mantener la consistencia
    if generos_principales:
        serie.generos = ", ".join(generos_principales[:3])
    
    try:
        serie.save(update_fields=["titulo", "sinopsis", "poster_path", "backdrop_path", "calificacion", "fecha_estreno", "total_capitulos", "total_temporadas", "generos"])
    except Exception: pass

    lista_episodios = []
    url_temporada = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{num_temporada}?api_key={API_KEY_TMDB}&language=es-MX"
    try:
        res_temp = requests.get(url_temporada, timeout=3.0)
        if res_temp.status_code == 200:
            lista_episodios = res_temp.json().get("episodes", [])
    except Exception: pass

    actores_totales, staff_totales = procesar_creditos_api(tmdb_id, num_temporada)
    detalles_produccion = inferir_detalles_produccion(datos_gen)

    contexto = {
        "serie": serie,
        "episodios": lista_episodios,
        "total_episodios": len(lista_episodios),
        "total_capitulos_serie": serie.total_capitulos,
        "total_temporadas": total_temporadas,
        "calificacion_real": serie.calificacion,
        "fecha_estreno_real": serie.fecha_estreno,
        "temporada_actual": num_temporada,
        "generos_principales": generos_principales[:3],
        "nanogeneros": generos_principales[:3],
        "personajes": [],
        "alcanzo_limite_personajes": False,
        "amigos_con_estado": [],
        "rango_temporadas": range(1, total_temporadas + 1),
        "detalles_produccion": detalles_produccion,
        "actores": actores_totales,
        "staff": staff_totales,
        "actores_visibles": actores_totales[:5],
        "actores_ocultos": actores_totales[5:],
        "staff_visibles": staff_totales[:5],
        "staff_ocultos": staff_totales[5:],
        "progreso_usuario": progreso_usuario,
    }

    if request.GET.get("format") == "json":
        html = render_to_string("series/detalles/episodios_render.html", contexto, request=request)
        return JsonResponse({"html": html, "total_episodios": len(lista_episodios)})

    return render(request, "series/detalle.html", contexto)


@login_required(login_url="iniciar_sesion")
def guardar_progreso(request, serie_id):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método no permitido."}, status=405)

    serie = get_object_or_404(Serie, pk=serie_id)
    score_raw = request.POST.get("score", "").strip()
    
    try: score = float(score_raw) if score_raw else None
    except (ValueError, TypeError): score = None

    try: current_season = int(request.POST.get("current_season", 1))
    except (ValueError, TypeError): current_season = 1

    try: current_episode = int(request.POST.get("current_episode", 0))
    except (ValueError, TypeError): current_episode = 0

    status = request.POST.get("status", "").strip()
    if status not in {choice[0] for choice in UserSeriesProgress.Status.choices}:
        status = UserSeriesProgress.Status.WATCHING

    # 1. Guardamos o actualizamos en la biblioteca del usuario
    progreso, creado = UserSeriesProgress.objects.update_or_create(
        perfil=request.user.perfil,
        serie=serie,
        defaults={
            "status": status,
            "score": score,
            "comment": request.POST.get("comment", "").strip(),
            "current_season": current_season,
            "current_episode": current_episode,
        },
    )

    # 2. Sincronizamos y guardamos los datos exactos en la tarjeta de actividad
    HistorialActividad.objects.create(
        perfil=request.user.perfil,
        serie=serie,
        accion=status,                       # Pasa el estado (watching, completed, etc.)
        score_momento=score,                 # Pasa la puntuación decimal o None
        comment_momento=progreso.comment     # Pasa el comentario limpio
    )

    return JsonResponse({"status": "success", "nuevo_estado": progreso.status, "texto_estado": progreso.get_status_display()})

# ============================================================
# 2. EXPLORACIÓN Y CATÁLOGO PRINCIPAL (INDEX / BUSCADOR)
# ============================================================

def index_invitado(request):
    hoy = datetime.date.today()
    bloque_semanal = hoy.toordinal() // 7
    generos_map = obtener_generos_tmdb(API_KEY_TMDB)
    
    url_base_discover = (
        f"https://api.themoviedb.org/3/discover/tv?api_key={API_KEY_TMDB}&language=es-MX"
        f"&include_image_language=en&with_genres=16&without_original_languages=ja,ko,zh,cn"
        f"&without_keywords=210024|161919&include_adult=false"
    )

    url_populares = f"{url_base_discover}&sort_by=popularity.desc&with_type=2|4"
    url_novedades = f"{url_base_discover}&sort_by=first_air_date.desc&first_air_date.lte={hoy.isoformat()}&with_type=2|4"
    url_mejor_valoradas = f"{url_base_discover}&sort_by=vote_average.desc&vote_count.gte=150&with_type=2|4"

    def _procesar_lista_api(url_origen, max_items=8):
        lista_limpia = []
        try:
            resultados = requests.get(url_origen, timeout=2.0).json().get("results", [])
            for item in resultados:
                if len(lista_limpia) >= max_items: break

                titulo = (item.get("name") or item.get("original_name") or "").lower()
                overview = (item.get("overview") or "").lower()

                if any(p in titulo or p in overview for p in PALABRAS_PROHIBIDAS): continue
                if item.get("original_language") in ["ja", "ko", "zh", "cn"]: continue

                g_nombres = [generos_map.get(gid) for gid in item.get("genre_ids", []) if gid in generos_map]
                sid = item.get("id")
                
                # Cambiado 'calificacion' por 'nota' para solucionar el problema del popover y el badge
                lista_limpia.append({
                    "id": sid,
                    "id_tmdb": sid,
                    "titulo": item.get("name"),
                    "poster_path": "https://image.tmdb.org/t/p/w500" + item["poster_path"] if item.get("poster_path") else DEFAULT_POSTER,
                    "nota": round(item.get("vote_average", 0.0), 1),
                    "fecha_estreno": item.get("first_air_date", "S/D")[:4] if item.get("first_air_date") else "N/A",
                    "generos": ", ".join(g_nombres[:3]) if g_nombres else "Animación",
                    "total_temporadas": 1,
                })
        except Exception:
            pass
        return lista_limpia

    recomendacion = None
    try:
        random.seed(bloque_semanal)
        pagina_rec = random.randint(1, 3)
        opciones_validas = _procesar_lista_api(f"{url_populares}&page={pagina_rec}", max_items=20)
        
        if opciones_validas:
            elegida = random.choice(opciones_validas)
            id_tmdb = elegida["id_tmdb"]
            
            detalle = requests.get(f"https://api.themoviedb.org/3/tv/{id_tmdb}?api_key={API_KEY_TMDB}&language=es-MX", timeout=2.0).json()
            generos_list = [g.get("name", "").strip() for g in detalle.get("genres", []) if g.get("name")][:3]

            recomendacion = {
                "id": id_tmdb,
                "id_tmdb": id_tmdb,
                "titulo": detalle.get("name") or elegida["titulo"],
                "sinopsis": detalle.get("overview") or "Sin sinopsis disponible.",
                "poster_path": detalle.get("poster_path") or elegida["poster_path"],
                "backdrop_path": detalle.get("backdrop_path"),
                "total_temporadas": detalle.get("number_of_seasons") or 1, 
                "generos": " • ".join(generos_list) if generos_list else "Animación",
            }
            
            random.seed(None)
            p_rec = recomendacion.get("poster_path")
            b_rec = recomendacion.get("backdrop_path")
            
            Serie.objects.update_or_create(
                id_tmdb=id_tmdb,
                defaults={
                    "titulo": detalle.get("original_name") or recomendacion["titulo"],
                    "sinopsis": recomendacion["sinopsis"],
                    "poster_path": "https://image.tmdb.org/t/p/w500" + p_rec if p_rec and not p_rec.startswith("http") else p_rec or DEFAULT_POSTER,
                    "backdrop_path": "https://image.tmdb.org/t/p/original" + b_rec if b_rec else None,
                    "total_capitulos": detalle.get("number_of_episodes", 0),
                    "total_temporadas": recomendacion["total_temporadas"],
                    "generos": recomendacion["generos"],
                },
            )
    except Exception:
        recomendacion = None

    tendencias_limpias = _procesar_lista_api(url_populares, max_items=8)
    novedades_limpias = _procesar_lista_api(url_novedades, max_items=8)
    mejor_valoradas_limpias = _procesar_lista_api(url_mejor_valoradas, max_items=8)

    mis_series_filtradas = []
    for s in Serie.objects.all():
        if any(p in (s.titulo or "").lower() or p in (s.generos or "").lower() for p in PALABRAS_PROHIBIDAS): continue
        mis_series_filtradas.append({
            "id": s.id_tmdb or s.id,
            "id_tmdb": s.id_tmdb or s.id,
            "titulo": s.titulo,
            "poster_path": s.poster_path,
            "nota": s.calificacion,
            "generos": ", ".join([g.strip() for g in s.generos.split(",")][:3]) if s.generos else "Animación",
            "total_temporadas": s.total_temporadas or 1,
            "fecha_estreno": s.fecha_estreno if s.fecha_estreno else "",
        })

    contexto = {
        "recomendacion": recomendacion,
        "tendencias": tendencias_limpias,
        "novedades": novedades_limpias,
        "mejor_valoradas": mejor_valoradas_limpias,
        "mis_series": mis_series_filtradas,
    }
    return render(request, "series/index.html", contexto)


def buscar_series(request):
    query = request.GET.get("q", "").strip()
    orden = request.GET.get("orden", "populares")
    page_number = int(request.GET.get("page", 1))
    resultados_finales = []
    has_next = False
    total_pages = 1

    if query:
        url = f"https://api.themoviedb.org/3/search/tv?api_key={API_KEY_TMDB}&language=es-MX&query={query}&page={page_number}&include_adult=true"
        try:
            res = requests.get(url, timeout=5.0)
            if res.status_code == 200:
                datos = res.json()
                total_pages = datos.get("total_pages", 1)
                has_next = page_number < total_pages
                for item in datos.get("results", []):
                    if 16 in item.get("genre_ids", []) and item.get("original_language", "") not in IDIOMAS_BLOQUEADOS:
                        resultados_finales.append(item)
        except Exception: pass
    else:
        url = f"https://api.themoviedb.org/3/discover/tv?api_key={API_KEY_TMDB}&language=es-MX&with_genres=16&without_original_languages=ja,ko,zh,cn&without_keywords=210024&page={page_number}&include_adult=true"
        if orden == "puntuacion": url += "&sort_by=vote_average.desc"
        elif orden == "recientes": url += "&sort_by=first_air_date.desc"
        else: url += "&sort_by=popularity.desc"
        try:
            res = requests.get(url, timeout=5.0)
            if res.status_code == 200:
                datos = res.json()
                total_pages = datos.get("total_pages", 1)
                has_next = page_number < total_pages
                resultados_finales = datos.get("results", [])
        except Exception: pass

    progresos_usuario = {}
    if request.user.is_authenticated:
        progresos_usuario = {p.serie.id_tmdb: p.status for p in UserSeriesProgress.objects.filter(perfil=request.user.perfil).select_related('serie') if p.serie.id_tmdb}

    generos_map = obtener_generos_tmdb(API_KEY_TMDB)
    lista_render = []
    for item in resultados_finales:
        titulo = (item.get("name") or item.get("original_name") or "").lower()
        overview = (item.get("overview") or "").lower()
        
        # Corregido: cambiada a PALABRAS_PROHIBIDAS en mayúsculas para usar la constante global
        if any(p in titulo or p in overview for p in PALABRAS_PROHIBIDAS): 
            continue
        if item.get("original_language") in ["ja", "ko", "zh", "cn"]: 
            continue

        g_nombres = [generos_map.get(gid) for gid in item.get("genre_ids", []) if gid in generos_map]
        id_tmdb_actual = item.get("id")
        poster_raw = item.get("poster_path")

        lista_render.append({
            "id_tmdb": id_tmdb_actual,
            "id": id_tmdb_actual,
            "titulo": item.get("name") or item.get("original_name"),
            "poster_path": f"https://image.tmdb.org/t/p/w500{poster_raw}" if poster_raw else DEFAULT_POSTER,
            "calificacion": round(item.get("vote_average", 0), 1),
            "nota": round(item.get("vote_average", 0), 1),
            "total_temporadas": 1,
            "generos": ", ".join(g_nombres[:3]) if g_nombres else "Animación",
            "anio": item.get("first_air_date", "")[:4] if item.get("first_air_date") else "N/A",
            "estado_biblioteca": progresos_usuario.get(id_tmdb_actual, None),
        })

    if request.GET.get("format") == "json":
        html = render_to_string("series/includes/tarjeta_explorar.html", {"resultados": lista_render}, request=request)
        return JsonResponse({"html": html, "has_next": has_next, "page": page_number, "total_pages": total_pages})

    return render(request, "series/resultados_busqueda.html", {"resultados": lista_render, "busqueda": query, "page": page_number, "has_next": has_next})

# ============================================================
# 3. GESTIÓN ADMINISTRATIVA (CREACIÓN Y ELIMINACIÓN)
# ============================================================

def crear_serie(request):
    if request.method == "POST":
        nombre_buscar = request.POST.get("titulo")
        url = f"https://api.themoviedb.org/3/search/tv?api_key={API_KEY_TMDB}&query={nombre_buscar}&language=en-US"
        try:
            datos = requests.get(url, timeout=3.0).json()
        except Exception:
            return redirect("index_invitado")

        if datos.get("results"):
            resultado = datos["results"][0]
            id_serie = resultado.get("id")

            # Verificar si la serie ya existe localmente para no duplicarla
            serie_local = Serie.objects.filter(id_tmdb=id_serie).first()

            if not serie_local:
                url_detalle = f"https://api.themoviedb.org/3/tv/{id_serie}?api_key={API_KEY_TMDB}&language=en-US"
                try:
                    datos_detalle = requests.get(url_detalle, timeout=3.0).json()
                    if 16 not in [g["id"] for g in datos_detalle.get("genres", [])] or datos_detalle.get("original_language", "") in IDIOMAS_BLOQUEADOS:
                        return redirect("index_invitado")

                    lista_generos = datos_detalle.get("genres", [])
                    poster_raw = datos_detalle.get("poster_path")
                    backdrop_raw = datos_detalle.get("backdrop_path")

                    # Creamos la serie de forma limpia
                    serie_local = Serie.objects.create(
                        titulo=datos_detalle.get("original_name") or datos_detalle.get("name"),
                        id_tmdb=id_serie,
                        sinopsis=datos_detalle.get("overview") or "No se encontró sinopsis.",
                        calificacion=datos_detalle.get("vote_average", 0.0),
                        poster_path="https://image.tmdb.org/t/p/w500" + poster_raw if poster_raw else DEFAULT_POSTER,
                        backdrop_path="https://image.tmdb.org/t/p/original" + backdrop_raw if backdrop_raw else "",
                        fecha_estreno=datos_detalle.get("first_air_date", "S/D"),
                        generos=", ".join([g["name"] for g in lista_generos][:3]) if lista_generos else "Animación",
                        total_capitulos=datos_detalle.get("number_of_episodes", 0),
                        total_temporadas=datos_detalle.get("number_of_seasons", 1),
                    )
                except Exception:
                    return redirect("index_invitado")

            # ============================================================
            # MAGIA: Asociar la serie al usuario actual que la está buscando
            # ============================================================
            if request.user.is_authenticated and serie_local:
                perfil_usuario = request.user.perfil
                
                # Buscamos o creamos el progreso en la biblioteca para este usuario
                progreso, creado = UserSeriesProgress.objects.get_or_create(
                    perfil=perfil_usuario,
                    serie=serie_local,
                    defaults={'estado': 'viendo'} # O el estado por defecto que prefieras
                )
                
                # Si es un registro nuevo en su biblioteca, generamos explícitamente la tarjeta de actividad
                if creado:
                    HistorialActividad.objects.create(
                        perfil=perfil_usuario,
                        serie=serie_local,
                        accion='empezo', # Ajusta este string según las opciones de tu campo 'accion'
                        comment_momento="¡Añadida a mi biblioteca desde el buscador!"
                    )

        return redirect("index_invitado")
    return render(request, "series/nueva_serie.html")


def eliminar_serie(request, serie_id):
    get_object_or_404(Serie, pk=serie_id).delete()
    return redirect("index_invitado")


# ============================================================
# 4. SISTEMA DE AUTENTICACIÓN Y PERFILES
# ============================================================

def registro(request):
    if request.user.is_authenticated: return redirect("index_invitado")
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            login(request, form.save())
            return redirect("editar_perfil")
    else: form = RegistroForm()
    return render(request, "series/registro.html", {"form": form})


def iniciar_sesion(request):
    if request.user.is_authenticated: return redirect("index_invitado")
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)
            if user is None:
                try: user = authenticate(request, username=User.objects.get(email=username).username, password=password)
                except User.DoesNotExist: pass
            if user is not None:
                login(request, user)
                return redirect("index_invitado")
            form.add_error(None, "Usuario o contraseña incorrectos.")
    else: form = LoginForm()
    return render(request, "series/login.html", {"form": form})


def cerrar_sesion(request):
    logout(request)
    return redirect("index_invitado")


@login_required(login_url="iniciar_sesion")
def editar_perfil(request):
    perfil = request.user.perfil
    if request.method == "POST":
        form = ActualizarPerfilForm(request.POST, request.FILES, instance=perfil)
        if form.is_valid():
            form.save()
            return redirect("ver_perfil", username=request.user.username)
    else: form = ActualizarPerfilForm(instance=perfil)
    return render(request, "series/editar_perfil.html", {"form": form, "perfil": perfil})


def ver_perfil(request, username):
    usuario = get_object_or_404(User, username=username)
    perfil_usuario = usuario.perfil

    # Consulta limpia para la pestaña Actividad (sin el filtro incompleto de es_silencioso)
    actividades_reales = HistorialActividad.objects.filter(
        perfil=perfil_usuario
    ).select_related('serie').order_by('-id') # Añadido un ordenamiento por si acaso para mantener las recientes arriba

    # Determinamos el perfil del usuario autenticado de forma segura
    perfil_actual = None
    if request.user.is_authenticated:
        try:
            perfil_actual = request.user.perfil
        except Perfil.DoesNotExist:
            perfil_actual = None

    # Procesamos todas las tarjetas en un único bucle limpio
    for act in actividades_reales:
        # 1. Guardamos los contadores en atributos limpios
        act.total_likes = act.votos.filter(tipo='like').count()
        act.total_dislikes = act.votos.filter(tipo='dislike').count()
        
        # 2. Averiguamos si el usuario actual ya votó esta tarjeta
        if perfil_actual:
            voto = act.votos.filter(perfil=perfil_actual).first()
            act.voto_usuario = voto.tipo if voto else 'ninguno'
        else:
            act.voto_usuario = 'ninguno'

    # Consulta base de seguimiento de series para las pestañas Biblioteca, Favoritos y Aportes
    progresos_usuario = UserSeriesProgress.objects.filter(
        perfil=perfil_usuario
    ).select_related('serie')

    return render(request, "series/ver_perfil.html", {
        "usuario": usuario,
        "perfil": perfil_usuario,
        "es_propietario": request.user == usuario if request.user.is_authenticated else False,

        # Actividad
        "actividades": actividades_reales,

        # Biblioteca, favoritos y aportes
        "progresos": progresos_usuario,
        "progresos_usuario": progresos_usuario,
        "biblioteca": progresos_usuario,
        "favoritos": progresos_usuario,
        "aportes": progresos_usuario,

        # Estadísticas
        "stats": {
            "total_vistas": 24,
            "genero_top": "Aventura / Ciencia Ficción",
            "tag_top": "#AnimaciónOccidental"
        },

        "listas_personalizadas": [],
        "listas_episodios": [],
        "generos_disponibles": []
    })


def comunidad(request):
    return render(request, 'series/comunidad.html', {'notificaciones_count': 0})


# ============================================================
# 5. ACCIONES ASÍNCRONAS (AJAX)
# ============================================================

@login_required
@require_POST
def guardar_serie_rapido(request):
    try:
        data = json.loads(request.body)
        id_tmdb = data.get('id_tmdb')
        if not id_tmdb: return JsonResponse({'status': 'error', 'message': 'ID de TMDB faltante'}, status=400)

        serie_local, _ = Serie.objects.get_or_create(
            id_tmdb=id_tmdb,
            defaults={'titulo': data.get('titulo'), 'poster_path': data.get('poster_path')}
        )
        progress, creado = UserSeriesProgress.objects.get_or_create(
            perfil=request.user.perfil, serie=serie_local,
            defaults={'status': UserSeriesProgress.Status.PLAN_TO_WATCH}
        )
        return JsonResponse({
            'status': 'success', 'creado': creado, 'estado_actual': progress.status,
            'message': f'"{serie_local.titulo}" añadida correctamente a tu lista Por Ver.'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
def votar_actividad(request, actividad_id):
    try:
        # Obtenemos el perfil del usuario autenticado
        perfil_usuario = request.user.perfil  
        actividad = HistorialActividad.objects.get(id=actividad_id)
    except (Perfil.DoesNotExist, HistorialActividad.DoesNotExist):
        return JsonResponse({'error': 'Recurso no encontrado'}, status=404)

    # Obtenemos el tipo de voto enviado desde el frontend ('like' o 'dislike')
    tipo_voto = request.POST.get('tipo')
    if tipo_voto not in [VotoActividad.TipoVoto.LIKE, VotoActividad.TipoVoto.DISLIKE]:
        return JsonResponse({'error': 'Tipo de voto inválido'}, status=400)

    # Buscamos si ya existe un voto previo de este usuario en esta actividad
    voto_existente = VotoActividad.objects.filter(perfil=perfil_usuario, actividad=actividad).first()

    if voto_existente:
        if voto_existente.tipo == tipo_voto:
            # Regla: Si presiona el mismo botón que ya tenía activo, el voto se cancela (quita el voto)
            voto_existente.delete()
            estado_voto = 'removido'
        else:
            # Regla: Si cambia de opinión (de like a dislike o viceversa), se actualiza el tipo
            voto_existente.tipo = tipo_voto
            voto_existente.save()
            estado_voto = 'cambiado'
    else:
        # Regla: Si no había votado antes, se crea el nuevo registro
        VotoActividad.objects.create(perfil=perfil_usuario, actividad=actividad, tipo=tipo_voto)
        estado_voto = 'creado'

    # Calculamos los totales actualizados de la actividad para mandarlos de vuelta
    total_likes = actividad.votos.filter(tipo=VotoActividad.TipoVoto.LIKE).count()
    total_dislikes = actividad.votos.filter(tipo=VotoActividad.TipoVoto.DISLIKE).count()

    # Averiguamos qué voto tiene activo el usuario justo ahora para mandarlo al front-end
    voto_final = VotoActividad.objects.filter(perfil=perfil_usuario, actividad=actividad).first()
    voto_actual = voto_final.tipo if voto_final else 'ninguno'

    return JsonResponse({
        'status': 'success',
        'estado_voto': estado_voto,
        'likes': total_likes,
        'dislikes': total_dislikes,
        'voto_actual': voto_actual  # Devuelve: 'like', 'dislike' o 'ninguno'
    })

def obtener_comentarios(request, actividad_id):
    if request.method == 'GET':
        try:
            actividad = HistorialActividad.objects.get(id=actividad_id)
            comentarios = actividad.comentarios.all().select_related('usuario').order_by('-created_at')
            
            lista_comentarios = []
            for c in comentarios:
                usuario_foto = None
                if hasattr(c.usuario, 'perfil') and hasattr(c.usuario.perfil, 'foto_perfil') and c.usuario.perfil.foto_perfil:
                    usuario_foto = c.usuario.perfil.foto_perfil.url

                # Calculamos el tiempo transcurrido (ej: "5 minutes" o "1 day")
                tiempo_transcurrido = timesince(c.created_at, timezone.now())
                # Tomamos solo el primer componente para evitar cosas como "1 semana, 2 días"
                tiempo_limpio = tiempo_transcurrido.split(',')[0]
                fecha_relativa = f"hace {tiempo_limpio}"

                lista_comentarios.append({
                    'id': c.id,
                    'usuario': c.usuario.username,
                    'usuario_foto': usuario_foto,
                    'texto': c.texto,
                    'fecha': fecha_relativa, # Pasamos el formato corto y limpio
                })
                
            return JsonResponse({'status': 'success', 'comentarios': lista_comentarios})
        except HistorialActividad.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Actividad no encontrada'}, status=404)

@login_required
def agregar_comentario(request, actividad_id):
    if request.method == 'POST':
        texto = request.POST.get('texto', '').strip()
        if not texto:
            return JsonResponse({'status': 'error', 'message': 'El comentario no puede estar vacío'}, status=400)
            
        try:
            actividad = HistorialActividad.objects.get(id=actividad_id)
            nuevo_comentario = ComentarioActividad.objects.create(
                actividad=actividad,
                usuario=request.user,
                texto=texto
            )
            
            # Buscamos la foto directamente usando la relación del comentario recién guardado
            usuario_foto = None
            if hasattr(nuevo_comentario.usuario, 'perfil') and hasattr(nuevo_comentario.usuario.perfil, 'foto_perfil') and nuevo_comentario.usuario.perfil.foto_perfil:
                usuario_foto = nuevo_comentario.usuario.perfil.foto_perfil.url
            
            return JsonResponse({
                'status': 'success',
                'comentario': {
                    'id': nuevo_comentario.id,
                    'usuario': nuevo_comentario.usuario.username,
                    'usuario_foto': usuario_foto, # Enviamos la URL comprobada
                    'texto': nuevo_comentario.texto,
                    'fecha': f"hace {timesince(nuevo_comentario.created_at, timezone.now()).split(',')[0]}",
                },
                'total_comentarios': actividad.comentarios.count()
            })
        except HistorialActividad.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Actividad no encontrada'}, status=404)

@login_required
def comunidad(request):
    # 1. Traer toda la actividad automática de series
    actividades = HistorialActividad.objects.all().select_related('perfil__usuario', 'serie')
    # Marcamos estas tarjetas como 'actividad'
    for act in actividades:
        act.tipo_tarjeta = 'actividad'

    # 2. Traer todos los posts manuales de la comunidad
    posts_comunidad = ComunidadPost.objects.all().select_related('usuario', 'serie_vinculada', 'capitulo_vinculado').prefetch_related('opciones_encuesta')
    # Marcamos estas tarjetas según su tipo real en la base de datos ('foro', 'natural', 'encuesta')
    for post in posts_comunidad:
        post.tipo_tarjeta = post.tipo  # Copia el valor de tu campo 'tipo' (natural, foro, encuesta)

    # 3. Unificar ambos mundos reales en una sola lista en memoria
    feed_completo = list(actividades) + list(posts_comunidad)

    # 4. Ordenar cronológicamente: el más reciente primero
    feed_completo.sort(key=lambda x: x.created_at, reverse=True)

    # 5. Foros más activos para la barra lateral derecha
    foros_calientes = (
        ComunidadPost.objects.filter(tipo=ComunidadPost.TipoPost.FORO)
        .annotate(num_respuestas=Count('respuestas'))
        .order_by('-num_respuestas')[:4]
    )

    context = {
        'feed': feed_completo,
        'foros_calientes': foros_calientes,
    }

    return render(request, 'series/comunidad.html', context)