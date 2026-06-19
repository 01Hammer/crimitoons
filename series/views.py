import datetime
import requests
import json

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from .models import Serie, Perfil, UserSeriesProgress
from .forms import RegistroForm, LoginForm, ActualizarPerfilForm
from django.http import JsonResponse, Http404
from django.template.loader import render_to_string
from django.core.paginator import Paginator

DEFAULT_POSTER = "https://placehold.co/500x750/3D262B/F7F3E3?text=No+Poster"

# ============================================================
# HELPERS/UTILIDADES
# ============================================================


def obtener_generos_tmdb(api_key):
    url = f"https://api.themoviedb.org/3/genre/tv/list?api_key={api_key}&language=en-US"
    try:
        res = requests.get(url, timeout=2.0).json()
        return {g["id"]: g["name"] for g in res.get("genres", [])}
    except Exception:
        return {}


# ============================================================
# 1. DETALLE DE SERIE
# ============================================================


def detalle_serie(request, serie_id):
    api_key = "ea735303fe1aa8a04e298b1f9c130e6c"

    IDIOMAS_BLOQUEADOS = {"ja", "zh", "ko"}

    def _pelicula_vinculada_a_serie_animada(movie_id):
        try:
            url_movie = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}&language=en-US"
            res_movie = requests.get(url_movie, timeout=3.0)
            if res_movie.status_code != 200:
                return False
            datos_movie = res_movie.json()

            ids_genero_movie = [g["id"] for g in datos_movie.get("genres", [])]
            if 16 not in ids_genero_movie:
                return False

            idioma_movie = datos_movie.get("original_language", "")
            if idioma_movie in IDIOMAS_BLOQUEADOS:
                return False

            titulo_movie = datos_movie.get("original_title") or datos_movie.get("title", "")
            if not titulo_movie:
                return False

            url_busq = (
                f"https://api.themoviedb.org/3/search/tv?api_key={api_key}"
                f"&language=en-US&query={titulo_movie}"
            )
            res_busq = requests.get(url_busq, timeout=3.0)
            if res_busq.status_code == 200:
                for resultado in res_busq.json().get("results", []):
                    if 16 in resultado.get("genre_ids", []):
                        idioma_serie = resultado.get("original_language", "")
                        if idioma_serie not in IDIOMAS_BLOQUEADOS:
                            return True
        except Exception:
            pass
        return False

    serie = Serie.objects.filter(id_tmdb=serie_id).first()
    if serie is None:
        serie = Serie.objects.filter(id=serie_id).first()

    if serie is None:
        url_creacion = f"https://api.themoviedb.org/3/tv/{serie_id}?api_key={api_key}&language=en-US"
        try:
            res = requests.get(url_creacion, timeout=3.0)
            if res.status_code == 200:
                datos = res.json()

                idioma_original = datos.get("original_language", "")
                if idioma_original in IDIOMAS_BLOQUEADOS:
                    raise Http404("Este contenido no está disponible en este catálogo.")

                ids_genero = [g["id"] for g in datos.get("genres", [])]
                if 16 not in ids_genero:
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
            else:
                if _pelicula_vinculada_a_serie_animada(serie_id):
                    url_movie = f"https://api.themoviedb.org/3/movie/{serie_id}?api_key={api_key}&language=es-MX"
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
        except Http404:
            raise
        except Exception as e:
            raise Http404("Error al conectar con el servicio externo.")

    num_temporada = int(request.GET.get("temporada", 1))
    tmdb_id = getattr(serie, "id_tmdb", None)

    progreso_usuario = None
    if request.user.is_authenticated:
        try:
            progreso_usuario = UserSeriesProgress.objects.get(
                perfil=request.user.perfil,
                serie=serie,
            )
        except UserSeriesProgress.DoesNotExist:
            progreso_usuario = None

    if not tmdb_id:
        try:
            url_busqueda = (
                f"https://api.themoviedb.org/3/search/tv?api_key={api_key}"
                f"&query={serie.titulo}&language=es-MX"
            )
            res_busqueda = requests.get(url_busqueda, timeout=3.0)
            if res_busqueda.status_code == 200:
                resultados = res_busqueda.json().get("results", [])
                if resultados:
                    tmdb_id = resultados[0].get("id")
        except Exception:
            pass

    total_temporadas = 1
    datos_gen = {}
    generos_principales = []
    calificacion_real = serie.calificacion
    total_capitulos_serie = serie.total_capitulos
    fecha_estreno_real = serie.fecha_estreno
    sinopsis_dinamica = serie.sinopsis
    poster_dinamico = serie.poster_path
    banner_dinamico = serie.backdrop_path
    nanogeneros = []

    url_general = (
        f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={api_key}"
        f"&language=es-MX&append_to_response=content_ratings"
    )
    try:
        response_gen = requests.get(url_general, timeout=3.0)
        if response_gen.status_code == 200:
            datos_gen = response_gen.json()
            total_temporadas = datos_gen.get("number_of_seasons", 1)
            generos_principales = [
                g.get("name", "") for g in datos_gen.get("genres", []) if g.get("name")
            ]
            calificacion_real = datos_gen.get("vote_average") or calificacion_real
            total_capitulos_serie = (
                datos_gen.get("number_of_episodes") or total_capitulos_serie
            )
            fecha_estreno_real = datos_gen.get("first_air_date") or fecha_estreno_real
            sinopsis_dinamica = datos_gen.get("overview") or sinopsis_dinamica
            
            poster_es = datos_gen.get("poster_path")
            if poster_es:
                poster_dinamico = "https://image.tmdb.org/t/p/w500" + poster_es
            banner_es = datos_gen.get("backdrop_path")
            if banner_es:
                banner_dinamico = "https://image.tmdb.org/t/p/original" + banner_es
    except Exception:
        pass

    url_ingles = (
        f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={api_key}"
        f"&language=en-US&include_image_language=en,null"
    )
    try:
        response_en = requests.get(url_ingles, timeout=3.0)
        if response_en.status_code == 200:
            datos_en = response_en.json()
            titulo_en = datos_en.get("original_name") or datos_en.get("name")
            if titulo_en:
                serie.titulo = titulo_en
            
            poster_en = datos_en.get("poster_path")
            if poster_en and not datos_gen.get("poster_path"):
                poster_dinamico = "https://image.tmdb.org/t/p/w500" + poster_en
                
            banner_en = datos_en.get("backdrop_path")
            if banner_en and not datos_gen.get("backdrop_path"):
                banner_dinamico = "https://image.tmdb.org/t/p/original" + banner_en
    except Exception:
        pass

    if not poster_dinamico:
        poster_dinamico = DEFAULT_POSTER

    serie.sinopsis = sinopsis_dinamica
    serie.poster_path = poster_dinamico
    serie.backdrop_path = banner_dinamico
    serie.calificacion = calificacion_real
    serie.fecha_estreno = fecha_estreno_real
    serie.total_capitulos = total_capitulos_serie
    serie.total_temporadas = total_temporadas
    if generos_principales:
        serie.generos = ", ".join(generos_principales)
    
    try:
        serie.save(update_fields=["titulo", "sinopsis", "poster_path", "backdrop_path", "calificacion", "fecha_estreno", "total_capitulos", "total_temporadas", "generos"])
    except Exception:
        pass

    if not nanogeneros:
        nanogeneros = generos_principales[:]

    lista_episodios = []
    total_episodios = 0
    url_temporada = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{num_temporada}?api_key={api_key}&language=es-MX"
    try:
        response_temp = requests.get(url_temporada, timeout=3.0)
        if response_temp.status_code == 200:
            datos_temp = response_temp.json()
            lista_episodios = datos_temp.get("episodes", [])
            total_episodios = len(lista_episodios)
    except Exception:
        pass

    TIMEOUT_CREDITOS = 5.0
    diccionario_actores = {}
    diccionario_staff = {}

    MAPA_NOMBRES = {
        "mum": "Johanna",
        "wood man": "Hombre de Madera",
        "the librarian": "Kaisa (Bibliotecaria)",
        "librarian": "Kaisa (Bibliotecaria)",
    }

    def _limpiar_personaje(personaje_sucio):
        limpio = (personaje_sucio or "").replace(" (voice)", "").split(" / ")[0].strip()
        if not limpio:
            return "Sin especificar"
        return MAPA_NOMBRES.get(limpio.lower(), limpio)

    def _procesar_actor(persona, personaje_nombre=None):
        id_actor = persona.get("id")
        if not id_actor:
            return
        if personaje_nombre is None:
            personaje_nombre = persona.get("character") or ""
        personaje_limpio = _limpiar_personaje(personaje_nombre)
        if id_actor not in diccionario_actores:
            diccionario_actores[id_actor] = {
                "nombre": persona.get("name"),
                "personaje": personaje_limpio,
                "foto_path": persona.get("profile_path"),
            }
        elif personaje_limpio not in diccionario_actores[id_actor]["personaje"]:
            diccionario_actores[id_actor]["personaje"] += f", {personaje_limpio}"

    def _procesar_staff(persona, rol_nombre=None):
        id_staff = persona.get("id")
        if not id_staff:
            return
        if rol_nombre is None:
            rol_nombre = (
                persona.get("job") or persona.get("department") or "Sin especificar"
            )
        if id_staff not in diccionario_staff:
            diccionario_staff[id_staff] = {
                "nombre": persona.get("name"),
                "roles_lista": [rol_nombre],
                "foto_path": persona.get("profile_path"),
            }
        elif rol_nombre not in diccionario_staff[id_staff]["roles_lista"]:
            diccionario_staff[id_staff]["roles_lista"].append(rol_nombre)

    url_creditos_serie = f"https://api.themoviedb.org/3/tv/{tmdb_id}/aggregate_credits?api_key={api_key}&language=es-MX"
    creditos_ok = False
    try:
        res_creditos = requests.get(url_creditos_serie, timeout=TIMEOUT_CREDITOS)
        if res_creditos.status_code == 200:
            datos_creditos = res_creditos.json()
            for persona in datos_creditos.get("cast", []):
                roles = persona.get("roles") or []
                if not roles:
                    _procesar_actor(persona, "")
                for r in roles:
                    _procesar_actor(persona, r.get("character"))
            for persona in datos_creditos.get("crew", []):
                jobs = persona.get("jobs") or []
                if not jobs:
                    _procesar_staff(
                        persona,
                        persona.get("known_for_department")
                        or persona.get("department"),
                    )
                for j in jobs:
                    _procesar_staff(persona, j.get("job"))
            creditos_ok = bool(diccionario_actores or diccionario_staff)
    except Exception:
        pass

    if not creditos_ok:
        url_creditos_temp = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{num_temporada}/credits?api_key={api_key}&language=es-MX"
        try:
            res_cred = requests.get(url_creditos_temp, timeout=TIMEOUT_CREDITOS)
            if res_cred.status_code == 200:
                datos_cred = res_cred.json()
                for cast in datos_cred.get("cast", []):
                    _procesar_actor(cast)
                for crew in datos_cred.get("crew", []):
                    _procesar_staff(crew)
        except Exception:
            pass

    actores_totales = sorted(
        diccionario_actores.values(), key=lambda a: (a["nombre"] or "").lower()
    )
    staff_totales = sorted(
        diccionario_staff.values(), key=lambda m: (m["nombre"] or "").lower()
    )
    actores_visibles, actors_ocultos = actores_totales[:5], actores_totales[5:]
    staff_visibles, staff_ocultos = staff_totales[:5], staff_totales[5:]

    MAPA_PAISES = {
        "US": "Estados Unidos",
        "CA": "Canadá",
        "JP": "Japón",
        "FR": "Francia",
        "KR": "Corea del Sur",
        "GB": "Reino Unido",
        "ES": "España",
        "MX": "México",
        "CO": "Colombia",
        "BR": "Brasil",
    }

    detalles_produccion = {
        "estudio": "No disponible",
        "pais": "No disponible",
        "tecnica": "Animación 2D",
        "publico": "Para todos los públicos (G)",
    }

    if datos_gen:
        networks = datos_gen.get("networks", [])
        if networks:
            detalles_produccion["estudio"] = networks[0].get("name")

        paises_origen = datos_gen.get("origin_country", [])
        paises_produccion = datos_gen.get("production_countries", [])
        codigo_pais = (
            paises_origen[0]
            if paises_origen
            else (paises_produccion[0].get("iso_3166_1") if paises_produccion else None)
        )
        if codigo_pais:
            detalles_produccion["pais"] = MAPA_PAISES.get(
                str(codigo_pais).upper().strip(), codigo_pais
            )

        ratings = datos_gen.get("content_ratings", {}).get("results", [])
        for r in ratings:
            if r.get("iso_3166_1") in ["US", "MX"]:
                rating_code = r.get("rating")
                if rating_code in ["TV-Y", "TV-G", "G"]:
                    detalles_produccion["publico"] = "Apto para todo público"
                elif rating_code in ["TV-Y7", "TV-Y7-FV", "PG"]:
                    detalles_produccion["publico"] = "Infantil / Juvenil (7+)"
                elif rating_code in ["TV-PG", "TV-14", "PG-13"]:
                    detalles_produccion["publico"] = "Adolescentes (14+)"
                elif rating_code in ["TV-MA", "R"]:
                    detalles_produccion["publico"] = "Animación Adulta (18+)"
                break

    personajes_home = []
    LIMITE_PERSONAJES = 20
    alcanzo_limite_personajes = len(personajes_home) >= LIMITE_PERSONAJES
    amigos_con_estado = []

    contexto = {
        "serie": serie,
        "episodios": lista_episodios,
        "total_episodios": total_episodios,
        "total_capitulos_serie": total_capitulos_serie,
        "total_temporadas": total_temporadas,
        "calificacion_real": calificacion_real,
        "fecha_estreno_real": fecha_estreno_real,
        "temporada_actual": num_temporada,
        "generos_principales": generos_principales,
        "nanogeneros": nanogeneros,
        "personajes": personajes_home,
        "alcanzo_limite_personajes": alcanzo_limite_personajes,
        "amigos_con_estado": amigos_con_estado,
        "rango_temporadas": range(1, total_temporadas + 1),
        "detalles_produccion": detalles_produccion,
        "actores": actores_totales,
        "staff": staff_totales,
        "actores_visibles": actores_visibles,
        "actores_ocultos": actors_ocultos,
        "staff_visibles": staff_visibles,
        "staff_ocultos": staff_ocultos,
        "progreso_usuario": progreso_usuario,
    }

    if request.GET.get("format") == "json":
        html_renderizado = render_to_string(
            "series/detalles/episodios_render.html", contexto, request=request
        )
        return JsonResponse(
            {"html": html_renderizado, "total_episodios": total_episodios}
        )

    return render(request, "series/detalle.html", contexto)


# ============================================================
# 2. GUARDAR PROGRESO (FORMULARIO DETALLE)
# ============================================================


@login_required(login_url="iniciar_sesion")
def guardar_progreso(request, serie_id):
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Método no permitido."},
            status=405,
        )

    serie = get_object_or_404(Serie, pk=serie_id)
    perfil = request.user.perfil

    status = request.POST.get("status", "").strip()
    score_raw = request.POST.get("score", "").strip()
    comment = request.POST.get("comment", "").strip()
    current_season_raw = request.POST.get("current_season", "").strip()
    current_episode_raw = request.POST.get("current_episode", "").strip()

    score = None
    if score_raw:
        try:
            score = float(score_raw)
        except (ValueError, TypeError):
            score = None

    try:
        current_season = int(current_season_raw) if current_season_raw else 1
    except (ValueError, TypeError):
        current_season = 1

    try:
        current_episode = int(current_episode_raw) if current_episode_raw else 0
    except (ValueError, TypeError):
        current_episode = 0

    valid_statuses = {choice[0] for choice in UserSeriesProgress.Status.choices}
    if status not in valid_statuses:
        status = UserSeriesProgress.Status.WATCHING

    progreso, _ = UserSeriesProgress.objects.update_or_create(
        perfil=perfil,
        serie=serie,
        defaults={
            "status": status,
            "score": score,
            "comment": comment,
            "current_season": current_season,
            "current_episode": current_episode,
        },
    )

    return JsonResponse(
        {
            "status": "success",
            "nuevo_estado": progreso.status,
            "texto_estado": progreso.get_status_display(),
        }
    )


# ============================================================
# 3. GESTIÓN DE SERIES (ADMIN/CREACIÓN)
# ============================================================


def crear_serie(request):
    if request.method == "POST":
        nombre_buscar = request.POST.get("titulo")
        api_key = "ea735303fe1aa8a04e298b1f9c130e6c"

        url = f"https://api.themoviedb.org/3/search/tv?api_key={api_key}&query={nombre_buscar}&language=en-US"
        try:
            datos = requests.get(url, timeout=3.0).json()
        except Exception:
            return redirect("index_invitado")

        titulo_final = nombre_buscar
        sinopsis_final = "No se encontró sinopsis en español."
        poster_final = DEFAULT_POSTER
        banner_final = ""
        fecha_final = "S/D"
        generos_final = "No especificado"
        capitulos_final = 0
        temporadas_final = None
        nota_global_tmdb = 0.0
        id_serie = None

        if datos.get("results"):
            resultado = datos["results"][0]
            titulo_final = resultado.get("original_name") or resultado.get("name", nombre_buscar)
            poster_raw = resultado.get("poster_path", "")
            poster_final = "https://image.tmdb.org/t/p/w500" + poster_raw if poster_raw else DEFAULT_POSTER
            banner_raw = resultado.get("backdrop_path", "")
            banner_final = "https://image.tmdb.org/t/p/original" + banner_raw if banner_raw else ""
            fecha_final = resultado.get("first_air_date", "S/D")
            nota_global_tmdb = resultado.get("vote_average", 0.0)
            id_serie = resultado.get("id")

            url_detalle = f"https://api.themoviedb.org/3/tv/{id_serie}?api_key={api_key}&language=en-US"
            try:
                datos_detalle = requests.get(url_detalle, timeout=3.0).json()
                lista_generos = datos_detalle.get("genres", [])
                ids_generos = [g["id"] for g in lista_generos]

                if 16 not in ids_generos:
                    return redirect("index_invitado")

                idioma_serie = datos_detalle.get("original_language", "")
                if idioma_serie in {"ja", "zh", "ko"}:
                    return redirect("index_invitado")

                tipo_serie = datos_detalle.get("type", "")
                if tipo_serie == "Scripted":
                    return redirect("index_invitado")

                if datos_detalle.get("overview"):
                    sinopsis_final = datos_detalle["overview"]
                capitulos_final = datos_detalle.get("number_of_episodes", 0)
                temporadas_final = datos_detalle.get("number_of_seasons")
                if lista_generos:
                    generos_final = ", ".join([g["name"] for g in lista_generos])
                nota_global_tmdb = datos_detalle.get("vote_average", nota_global_tmdb)
                if datos_detalle.get("backdrop_path"):
                    banner_final = "https://image.tmdb.org/t/p/original" + datos_detalle["backdrop_path"]
            except Exception:
                return redirect("index_invitado")

        Serie.objects.create(
            titulo=titulo_final,
            id_tmdb=id_serie,
            sinopsis=sinopsis_final,
            calificacion=nota_global_tmdb,
            poster_path=poster_final,
            backdrop_path=banner_final,
            fecha_estreno=fecha_final,
            generos=generos_final,
            total_capitulos=capitulos_final,
            total_temporadas=temporadas_final,
        )
        return redirect("index_invitado")

    return render(request, "series/nueva_serie.html")


def eliminar_serie(request, serie_id):
    serie = get_object_or_404(Serie, pk=serie_id)
    serie.delete()
    return redirect("index_invitado")


# ============================================================
# 4. PÁGINA PRINCIPAL Y EXPLORAR
# ============================================================


def index_invitado(request):
    api_key = "ea735303fe1aa8a04e298b1f9c130e6c"
    hoy = datetime.date.today()
    bloque_semanal = hoy.toordinal() // 7

    generos_map = obtener_generos_tmdb(api_key)
    
    exclude_keywords = "210024|161919"
    
    url_base_discover = (
        f"https://api.themoviedb.org/3/discover/tv?api_key={api_key}&language=es-MX"
        f"&include_image_language=en&with_genres=16"
        f"&without_original_languages=ja,ko,zh,cn"
        f"&without_keywords={exclude_keywords}"
        f"&include_adult=false"
    )

    url_populares = f"{url_base_discover}&sort_by=popularity.desc&with_type=2|4"
    url_novedades = f"{url_base_discover}&sort_by=first_air_date.desc&first_air_date.lte={hoy.isoformat()}&with_type=2|4"
    url_mejor_valoradas = f"{url_base_discover}&sort_by=vote_average.desc&vote_count.gte=150&with_type=2|4"

    palabras_prohibidas = [
        "hentai", "ecchi", "yaoi", "yuri", "shota", "loli", 
        "adult animation", "erotic", "erótica", "nude", "nudity"
    ]

    def _limitar_generos(generos):
        return [genero for genero in generos if genero][:3]

    def _procesar_lista_api(url_origen, max_items=8):
        lista_limpia = []
        try:
            resultados = requests.get(url_origen, timeout=2.0).json().get("results", [])
            for item in resultados:
                if len(lista_limpia) >= max_items:
                    break

                titulo = (item.get("name") or item.get("original_name") or "").lower()
                overview = (item.get("overview") or "").lower()

                if any(p in titulo or p in overview for p in palabras_prohibidas):
                    continue

                if item.get("original_language") in ["ja", "ko", "zh", "cn"]:
                    continue

                g_nombres = [generos_map.get(gid) for gid in item.get("genre_ids", []) if gid in generos_map]
                sid = item.get("id")
                
                lista_limpia.append({
                    "id": sid,
                    "id_tmdb": sid,
                    "titulo": item.get("name"),
                    "poster_path": item.get("poster_path"),
                    "nota": item.get("vote_average", 0.0),
                    "fecha_estreno": item.get("first_air_date", "S/D")[:4] if item.get("first_air_date") else "N/A",
                    "generos": " • ".join(_limitar_generos(g_nombres)) if g_nombres else "Animation",
                    "total_capitulos": "Info en detalle",
                })
        except Exception:
            pass
        return lista_limpia

    recomendacion = None
    try:
        import random
        random.seed(bloque_semanal)
        pagina_recomendacion = random.randint(1, 3)
        
        opciones_validas = _procesar_lista_api(f"{url_populares}&page={pagina_recomendacion}", max_items=20)
        
        if opciones_validas:
            elegida = random.choice(opciones_validas)
            id_tmdb = elegida["id_tmdb"]
            
            detalle = requests.get(f"https://api.themoviedb.org/3/tv/{id_tmdb}?api_key={api_key}&language=es-MX", timeout=2.0).json()
            generos = _limitar_generos([genero.get("name", "").strip() for genero in detalle.get("genres", [])])

            recomendacion = {
                "id": id_tmdb,
                "id_tmdb": id_tmdb,
                "titulo": detalle.get("name") or elegida["titulo"],
                "sinopsis": detalle.get("overview") or "Sin sinopsis disponible.",
                "poster_path": detalle.get("poster_path") or elegida["poster_path"],
                "backdrop_path": detalle.get("backdrop_path"),
                "total_temporadas": detalle.get("number_of_seasons") or 1, 
                "generos": " • ".join(generos),
            }
            
            random.seed(None)
            poster_rec = recomendacion.get("poster_path")
            backdrop_rec = recomendacion.get("backdrop_path")
            
            Serie.objects.update_or_create(
                id_tmdb=id_tmdb,
                defaults={
                    "titulo": detalle.get("original_name") or recomendacion["titulo"],
                    "sinopsis": recomendacion["sinopsis"],
                    "poster_path": "https://image.tmdb.org/t/p/w500" + poster_rec if poster_rec else DEFAULT_POSTER,
                    "backdrop_path": "https://image.tmdb.org/t/p/original" + backdrop_rec if backdrop_rec else None,
                    "total_capitulos": detalle.get("number_of_episodes", 0),
                    "total_temporadas": detalle.get("number_of_seasons"),
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
        titulo_local = (s.titulo or "").lower()
        generos_local = (s.generos or "").lower()
        
        if any(p in titulo_local or p in generos_local for p in palabras_prohibidas):
            continue
            
        mis_series_filtradas.append({
            "id": s.id_tmdb if s.id_tmdb else s.id,
            "id_tmdb": s.id_tmdb if s.id_tmdb else s.id,
            "titulo": s.titulo,
            "poster_path": s.poster_path,
            "nota": s.calificacion,
            "generos": s.generos if s.generos else "Animation",
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
    api_key = "ea735303fe1aa8a04e298b1f9c130e6c"
    query = request.GET.get("q", "").strip()
    genero = request.GET.get("genero", "")
    orden = request.GET.get("orden", "populares")
    page_number = int(request.GET.get("page", 1))

    resultados_finales = []
    has_next = False
    total_pages = 1

    exclude_keywords = "210024"

    if query:
        url = (
            f"https://api.themoviedb.org/3/search/tv"
            f"?api_key={api_key}"
            f"&language=es-MX"
            f"&query={query}"
            f"&page={page_number}"
            f"&include_adult=true"
        )
        try:
            res = requests.get(url, timeout=5.0)
            if res.status_code == 200:
                datos = res.json()
                total_pages = datos.get("total_pages", 1)
                has_next = page_number < total_pages

                for item in datos.get("results", []):
                    genre_ids = item.get("genre_ids", [])
                    original_language = item.get("original_language", "")

                    if 16 in genre_ids and original_language not in ["ja", "ko", "zh", "cn"]:
                        resultados_finales.append(item)
        except Exception:
            pass

    else:
        url = (
            f"https://api.themoviedb.org/3/discover/tv"
            f"?api_key={api_key}"
            f"&language=es-MX"
            f"&with_genres=16"
            f"&without_original_languages=ja,ko,zh,cn"
            f"&without_keywords={exclude_keywords}"
            f"&page={page_number}"
            f"&include_adult=true"
        )

        if orden == "puntuacion":
            url += "&sort_by=vote_average.desc"
        elif orden == "recientes":
            url += "&sort_by=first_air_date.desc"
        else:
            url += "&sort_by=popularity.desc"

        try:
            res = requests.get(url, timeout=5.0)
            if res.status_code == 200:
                datos = res.json()
                total_pages = datos.get("total_pages", 1)
                has_next = page_number < total_pages
                resultados_finales = datos.get("results", [])
        except Exception:
            pass

    palabras_prohibidas = [
        "hentai", "ecchi", "yaoi", "yuri", "shota", "loli", 
        "adult animation", "erotic", "erótica", "nude", "nudity"
    ]

    progresos_usuario = {}
    if request.user.is_authenticated:
        progresos_usuario = {
            p.serie.id_tmdb: p.status 
            for p in UserSeriesProgress.objects.filter(perfil=request.user.perfil).select_related('serie')
            if p.serie.id_tmdb
        }

    lista_render = []
    for item in resultados_finales:
        titulo = (item.get("name") or item.get("original_name") or "").lower()
        overview = (item.get("overview") or "").lower()

        if any(palabra in titulo or palabra in overview for palabra in palabras_prohibidas):
            continue

        if item.get("original_language") in ["ja", "ko", "zh", "cn"]:
            continue

        id_tmdb_actual = item.get("id")
        poster_raw = item.get("poster_path")
        
        # Recuperamos el estado desde tu diccionario de progresos
        estado_local = progresos_usuario.get(id_tmdb_actual, None)

        lista_render.append({
            "id_tmdb": id_tmdb_actual,
            "titulo": item.get("name") or item.get("original_name"),
            "poster_path": f"https://image.tmdb.org/t/p/w500{poster_raw}" if poster_raw else None,
            "calificacion": round(item.get("vote_average", 0), 1),
            "anio": item.get("first_air_date", "")[:4] if item.get("first_air_date") else "",
            "estado_biblioteca": estado_local, # ¡ESTA ES LA LÍNEA CLAVE!
        })

    if request.GET.get("format") == "json":
        html = render_to_string(
            "series/includes/tarjeta_explorar.html",
            {"resultados": lista_render},
            request=request,
        )
        return JsonResponse({
            "html": html,
            "has_next": has_next,
            "page": page_number,
            "total_pages": total_pages,
        })

    return render(request, "series/resultados_busqueda.html", {
        "resultados": lista_render,
        "busqueda": query,
        "page": page_number,
        "has_next": has_next,
    })


# ============================================================
# 5. AUTENTICACIÓN Y SISTEMA DE USUARIOS
# ============================================================


def registro(request):
    if request.user.is_authenticated:
        return redirect("index_invitado")

    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("editar_perfil")
    else:
        form = RegistroForm()

    return render(request, "series/registro.html", {"form": form})


def iniciar_sesion(request):
    if request.user.is_authenticated:
        return redirect("index_invitado")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)

            if user is None:
                try:
                    usuario = User.objects.get(email=username)
                    user = authenticate(
                        request, username=usuario.username, password=password
                    )
                except User.DoesNotExist:
                    pass

            if user is not None:
                login(request, user)
                return redirect("index_invitado")
            else:
                form.add_error(None, "Usuario o contraseña incorrectos.")
    else:
        form = LoginForm()

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
    else:
        form = ActualizarPerfilForm(instance=perfil)

    return render(
        request, "series/editar_perfil.html", {"form": form, "perfil": perfil}
    )


def ver_perfil(request, username):
    usuario = get_object_or_404(User, username=username)
    perfil = usuario.perfil

    progresos = UserSeriesProgress.objects.filter(perfil=perfil).select_related('serie')

    stats_usuario = {
        "total_vistas": 24,
        "genero_top": "Aventura / Ciencia Ficción",
        "tag_top": "#AnimaciónOccidental",
    }

    historial_actividad = [
        {
            "texto": 'Marcó como "Visto" el episodio 3 de Hilda.',
            "tiempo": "Hace 2 horas",
        },
        {
            "texto": 'Añadió Arcane a su lista de "Mis Series Guardadas".',
            "tiempo": "Ayer",
        },
        {"texto": "Escribió una reseña en Amphibia.", "tiempo": "Hace 3 días"},
    ]

    return render(
        request,
        "series/ver_perfil.html",
        {
            "usuario": usuario,
            "perfil": perfil,
            "progresos": progresos,
            "es_propietario": request.user == usuario if request.user.is_authenticated else False,
            "stats": stats_usuario,
            "actividad": historial_actividad,
            "listas_personalizadas": [],
            "listas_episodios": [],
            "generos_disponibles": [],
        },
    )


def comunidad(request):
    context = {
        'notificaciones_count': 0,
    }
    return render(request, 'series/comunidad.html', context)


# ============================================================
# 6. ACCIONES ASÍNCRONAS (AJAX)
# ============================================================


@login_required
@require_POST
def guardar_serie_rapido(request):
    try:
        data = json.loads(request.body)
        id_tmdb = data.get('id_tmdb')
        titulo = data.get('titulo')
        poster_path = data.get('poster_path')

        if not id_tmdb:
            return JsonResponse({'status': 'error', 'message': 'ID de TMDB faltante'}, status=400)

        serie_local, creado = Serie.objects.get_or_create(
            id_tmdb=id_tmdb,
            defaults={
                'titulo': titulo,
                'poster_path': poster_path,
            }
        )

        perfil_usuario = request.user.perfil

        progress, progress_creado = UserSeriesProgress.objects.get_or_create(
            perfil=perfil_usuario,
            serie=serie_local,
            defaults={
                'status': UserSeriesProgress.Status.PLAN_TO_WATCH
            }
        )

        return JsonResponse({
            'status': 'success',
            'creado': progress_creado,
            'estado_actual': progress.status,
            'message': f'"{serie_local.titulo}" añadida correctamente a tu lista Por Ver.'
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)