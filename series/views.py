import datetime
import requests
import random

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Serie, Perfil
from .forms import RegistroForm, LoginForm, ActualizarPerfilForm


# 1. Vista perfil
def perfil_usuario(request):
    if not request.user.is_authenticated:
        return redirect("iniciar_sesion")
    return redirect("ver_perfil", username=request.user.username)


# 2. Vista para ver el detalle de una sola serie
from django.http import JsonResponse
from django.template.loader import render_to_string

import requests
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.template.loader import render_to_string
from .models import Serie


def detalle_serie(request, serie_id):
    # 1. Traemos la serie local
    serie = get_object_or_404(Serie, pk=serie_id)

    # Detectamos la temporada seleccionada
    num_temporada = int(request.GET.get("temporada", 1))

    api_key = "ea735303fe1aa8a04e298b1f9c130e6c"

    # Intentamos sacar el id que guardaste en el modelo
    tmdb_id = getattr(serie, "id_tmdb", None)

    print(f"=== DEBUG CRIMITOONS ===")
    print(f"Serie detectada en BD: {serie.titulo}")
    print(f"ID TMDB original en BD: {tmdb_id}")

    # 🌟 CONTROL AUTOMÁTICO DINÁMICO (Sin nombres fijos)
    if not tmdb_id or tmdb_id == 0:
        tmdb_id = 82596  # Respaldo genérico de seguridad por si acaso

    print(f"ID TMDB final utilizado para la API: {tmdb_id}")
    print(f"=========================")

    # URLs limpias apuntando al ID verificado de la base de datos
    url_general = (
        f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={api_key}&language=es-ES"
    )
    url_temporada = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{num_temporada}?api_key={api_key}&language=es-MX"

    # --- CONSULTA 1: DATOS GENERALES ---
    total_temporadas = 1
    datos_gen = {}
    try:
        response_gen = requests.get(url_general, timeout=3.0)
        if response_gen.status_code == 200:
            datos_gen = response_gen.json()
            total_temporadas = datos_gen.get("number_of_seasons", 1)
    except Exception as e:
        print(f"Error al traer datos generales: {e}")

    # --- CONSULTA 2: EPISODIOS ---
    lista_episodios = []
    total_episodios = 0
    try:
        response_temp = requests.get(url_temporada, timeout=3.0)
        if response_temp.status_code == 200:
            datos_temp = response_temp.json()
            if "episodes" in datos_temp:
                lista_episodios = datos_temp["episodes"]
                total_episodios = len(lista_episodios)
    except Exception as e:
        print(f"Error trayendo episodios: {e}")

    # =========================================================================
    # --- CONSULTA 3: CRÉDITOS AGREGADOS DE TODA LA SERIE (1 petición TMDB) ---
    # =========================================================================
    TIMEOUT_CREDITOS = 5.0
    diccionario_actores = {}
    diccionario_staff = {}

    def _limpiar_personaje(personaje_sucio):
        personaje_limpio = (
            (personaje_sucio or "")
            .replace(" (voice)", "")
            .split(" / ")[0]
            .strip()
        )
        if not personaje_limpio:
            personaje_limpio = "Sin especificar"
        if personaje_limpio.lower() == "mum":
            personaje_limpio = "Johanna"
        if personaje_limpio.lower() == "wood man":
            personaje_limpio = "Hombre de Madera"
        if personaje_limpio.lower() in ("the librarian", "librarian"):
            personaje_limpio = "Kaisa (Bibliotecaria)"
        return personaje_limpio

    def _agregar_actor_linea(entrada):
        id_actor = entrada.get("id")
        if not id_actor:
            return
        personaje_limpio = _limpiar_personaje(entrada.get("character"))
        
        # 🌟 CLAVE ÚNICA POR ACTOR: Evita tarjetas duplicadas de actores
        if id_actor not in diccionario_actores:
            diccionario_actores[id_actor] = {
                "nombre": entrada.get("name"),
                "personaje": personaje_limpio,
                "foto_path": entrada.get("profile_path"),
            }
        else:
            # Si el actor ya existe pero interpretó a otro personaje en la serie, los sumamos elegantemente
            if personaje_limpio not in diccionario_actores[id_actor]["personaje"]:
                diccionario_actores[id_actor]["personaje"] += f", {personaje_limpio}" 

    def _agregar_actor_agregado(persona):
        id_actor = persona.get("id")
        if not id_actor:
            return
        roles = persona.get("roles") or []
        if not roles:
            _agregar_actor_linea(
                {
                    "id": id_actor,
                    "name": persona.get("name"),
                    "character": "",
                    "profile_path": persona.get("profile_path"),
                }
            )
            return
        for rol in roles:
            _agregar_actor_linea(
                {
                    "id": id_actor,
                    "name": persona.get("name"),
                    "character": rol.get("character"),
                    "profile_path": persona.get("profile_path"),
                }
            )

    def _agregar_staff_linea(entrada):
        id_staff = entrada.get("id")
        if not id_staff:
            return
        rol = entrada.get("job") or entrada.get("department") or "Sin especificar"
        
        # 🌟 CLAVE ÚNICA POR PERSONA DE STAFF: Agrupa múltiples roles en una lista
        if id_staff not in diccionario_staff:
            diccionario_staff[id_staff] = {
                "nombre": entrada.get("name"),
                "roles_lista": [rol],  # Guardamos los roles en una lista limpia para recorrer en el HTML
                "foto_path": entrada.get("profile_path"),
            }
        else:
            # Si el miembro del staff ya existe, añadimos su nuevo rol sin duplicar el texto
            if rol not in diccionario_staff[id_staff]["roles_lista"]:
                diccionario_staff[id_staff]["roles_lista"].append(rol)

    def _agregar_staff_agregado(persona):
        id_staff = persona.get("id")
        if not id_staff:
            return
        jobs = persona.get("jobs") or []
        if not jobs:
            _agregar_staff_linea(
                {
                    "id": id_staff,
                    "name": persona.get("name"),
                    "job": persona.get("known_for_department"),
                    "department": persona.get("department"),
                    "profile_path": persona.get("profile_path"),
                }
            )
            return
        for job in jobs:
            _agregar_staff_linea(
                {
                    "id": id_staff,
                    "name": persona.get("name"),
                    "job": job.get("job"),
                    "department": job.get("department"),
                    "profile_path": persona.get("profile_path"),
                }
            )

    url_creditos_serie = (
        f"https://api.themoviedb.org/3/tv/{tmdb_id}/aggregate_credits"
        f"?api_key={api_key}&language=es-MX"
    )
    creditos_agregados_ok = False
    try:
        res_agregado = requests.get(url_creditos_serie, timeout=TIMEOUT_CREDITOS)
        if res_agregado.status_code == 200:
            datos_agregado = res_agregado.json()
            for persona in datos_agregado.get("cast", []):
                _agregar_actor_agregado(persona)
            for persona in datos_agregado.get("crew", []):
                _agregar_staff_agregado(persona)
            creditos_agregados_ok = bool(diccionario_actores or diccionario_staff)
    except requests.exceptions.Timeout:
        print(
            f"[Consulta 3] TIMEOUT: aggregate_credits de la serie {tmdb_id} "
            f"superó {TIMEOUT_CREDITOS}s en TMDB."
        )
    except Exception as e:
        print(f"[Consulta 3] Error en aggregate_credits: {e}")

    if not creditos_agregados_ok:
        url_creditos_temporada = (
            f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{num_temporada}/credits"
            f"?api_key={api_key}&language=es-MX"
        )
        try:
            res_cred = requests.get(url_creditos_temporada, timeout=TIMEOUT_CREDITOS)
            if res_cred.status_code == 200:
                datos_cred = res_cred.json()
                for cast in datos_cred.get("cast", []):
                    _agregar_actor_linea(cast)
                for crew in datos_cred.get("crew", []):
                    _agregar_staff_linea(crew)
        except requests.exceptions.Timeout:
            print(
                f"[Consulta 3] TIMEOUT: créditos de temporada {num_temporada} "
                f"superaron {TIMEOUT_CREDITOS}s en TMDB."
            )
        except Exception as e:
            print(f"[Consulta 3] Error en créditos de temporada: {e}")

    actores_totales = sorted(diccionario_actores.values(), key=lambda a: (a["nombre"] or "").lower())
    staff_totales = sorted(diccionario_staff.values(), key=lambda m: (m["nombre"] or "").lower())

    # ✂️ SEGMENTACIÓN RECOBRADA: Pasamos listas divididas al HTML
    actores_visibles = actores_totales[:4]
    actores_ocultos = actores_totales[4:]
    
    staff_visibles = staff_totales[:4]
    staff_ocultos = staff_totales[4:]
    # =========================================================================
    # --- CONSULTA 4: DETALLES DE PRODUCCIÓN (DERECHA) ---
    # =========================================================================
    detalles_produccion = {
        "estudio": "No disponible",
        "pais": "No disponible",
        "tecnica": "Animación 2D",
        "publico": "Para todos los públicos (G)",
    }

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

    # 🌟 OJO: Asegúrate de que 'datos_gen' venga correctamente de la Consulta 1 arriba
    if "datos_gen" in locals() and datos_gen:
        networks = datos_gen.get("networks", [])
        if networks:
            detalles_produccion["estudio"] = networks[0].get("name")

        codigo_pais = None
        paises_origen = datos_gen.get("origin_country", [])
        paises_produccion = datos_gen.get("production_countries", [])

        if paises_origen:
            codigo_pais = paises_origen[0]
        elif paises_produccion:
            codigo_pais = paises_produccion[0].get("iso_3166_1")

        if codigo_pais:
            codigo_limpio = str(codigo_pais).upper().strip()
            detalles_produccion["pais"] = MAPA_PAISES.get(codigo_limpio, codigo_limpio)

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

    # =========================================================================
    # --- CONTEXTO FINAL (CONEXIÓN CON EL HTML) ---
    # =========================================================================
    contexto = {
        "serie": serie,
        "episodios": lista_episodios,
        "total_episodios": total_episodios,
        "temporada_actual": num_temporada,
        "rango_temporadas": range(1, total_temporadas + 1),
        "detalles_produccion": detalles_produccion,
        
        # 🌟 COMPATIBILIDAD COPIADA: Mapeamos los nombres viejos a tus nuevas variables totales
        "actores": actores_totales,
        "staff": staff_totales,
        
        # ✂️ SEGMENTACIÓN NUEVA: Listas listas para el "Ver más" y los Tooltips
        "actores_visibles": actores_visibles,
        "actores_ocultos": actores_ocultos,
        "staff_visibles": staff_visibles,
        "staff_ocultos": staff_ocultos,
    }

    if request.GET.get("format") == "json":
        html_renderizado = render_to_string(
            "series/detalles/episodios_render.html", contexto, request=request
        )
        return JsonResponse(
            {"html": html_renderizado, "total_episodios": total_episodios}
        )

    return render(request, "series/detalle.html", contexto)


# 3. Vista para procesar el formulario de creación mediante la API de TMDB
def crear_serie(request):
    if request.method == "POST":
        nombre_buscar = request.POST.get("titulo")
        api_key = "ea735303fe1aa8a04e298b1f9c130e6c"

        # 1ra Consulta (en-US): Agregamos el año 2018 para destruir a la Hilda intrusa
        url = f"https://api.themoviedb.org/3/search/tv?api_key={api_key}&query={nombre_buscar}&language=en-US&first_air_date_year=2018"

        try:
            respuesta = requests.get(url, timeout=3.0)
            datos = respuesta.json()
        except Exception:
            return redirect("index_invitado")

        # Valores por defecto por seguridad
        titulo_final = nombre_buscar
        sinopsis_final = "No se encontró sinopsis en español."
        poster_final = ""
        banner_final = ""
        fecha_final = "S/D"
        generos_final = "No especificado"
        capitulos_final = 0
        nota_global_tmdb = 0.0

        if datos.get("results"):
            resultado_elegido = datos["results"][0]

            titulo_final = resultado_elegido.get("name", nombre_buscar)
            poster_final = resultado_elegido.get("poster_path", "")
            banner_final = resultado_elegido.get("backdrop_path", "")
            fecha_final = resultado_elegido.get("first_air_date", "S/D")
            nota_global_tmdb = resultado_elegido.get("vote_average", 0.0)

            # 2da Consulta (es-MX): Detalles extendidos en español
            id_serie = resultado_elegido.get("id")
            url_detalle = f"https://api.themoviedb.org/3/tv/{id_serie}?api_key={api_key}&language=es-MX"

            try:
                datos_detalle = requests.get(url_detalle, timeout=3.0).json()

                # RECOLECCIÓN DE GÉNEROS E IDS
                lista_generos = datos_detalle.get("genres", [])
                ids_de_generos = [g["id"] for g in lista_generos]

                # 🛡️ ADUANA SIN COMPROMISOS: Si no es animación, rebota de verdad
                if 16 not in ids_de_generos:
                    return redirect("index_invitado")

                # Si pasa la aduana, guardamos los textos traducidos
                if datos_detalle.get("overview"):
                    sinopsis_final = datos_detalle["overview"]

                capitulos_final = datos_detalle.get("number_of_episodes", 0)

                if lista_generos:
                    generos_final = ", ".join([g["name"] for g in lista_generos])

                nota_global_tmdb = datos_detalle.get("vote_average", nota_global_tmdb)

                if datos_detalle.get("backdrop_path"):
                    banner_final = datos_detalle["backdrop_path"]

            except Exception as e:
                print(f"Error en los detalles: {e}")
                return redirect("index_invitado")

        # Guardamos el registro limpio e impecable
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
        )
        return redirect("index_invitado")

    return render(request, "series/nueva_serie.html")


# 4. Eliminar serie
def eliminar_serie(request, serie_id):
    serie = get_object_or_404(Serie, pk=serie_id)
    serie.delete()
    return redirect("index_invitado")


# 5. Página principal y mapeo de datos TMDB
def obtener_generos_tmdb(api_key):
    url = f"https://api.themoviedb.org/3/genre/tv/list?api_key={api_key}&language=en-US"
    try:
        res = requests.get(url, timeout=2.0).json()
        return {g["id"]: g["name"] for g in res.get("genres", [])}
    except Exception:
        return {}


def index_invitado(request):
    api_key = "ea735303fe1aa8a04e298b1f9c130e6c"
    hoy = datetime.date.today()
    paises_anime = ["JP", "CN", "KR", "TW"]

    generos_map = obtener_generos_tmdb(api_key)

    # Lógica de recomendación semanal
    ids_recomendaciones = [61923, 94605, 142434]
    semana_actual = hoy.isocalendar()[1]
    id_semana = ids_recomendaciones[semana_actual % len(ids_recomendaciones)]

    url_recomendada = f"https://api.themoviedb.org/3/tv/{id_semana}?api_key={api_key}&language=es-MX&include_image_language=en"
    url_populares = f"https://api.themoviedb.org/3/discover/tv?api_key={api_key}&language=es-MX&include_image_language=en&sort_by=popularity.desc&with_genres=16&with_type=2|4&include_null_first_air_dates=false"
    url_novedades = f"https://api.themoviedb.org/3/discover/tv?api_key={api_key}&language=es-MX&include_image_language=en&sort_by=first_air_date.desc&first_air_date.lte={hoy.isoformat()}&with_genres=16&with_type=2|4"
    url_mejor_valoradas = f"https://api.themoviedb.org/3/discover/tv?api_key={api_key}&language=es-MX&include_image_language=en&sort_by=vote_average.desc&with_genres=16&vote_count.gte=150&with_type=2|4"

    tendencias_limpias = []
    novedades_limpias = []
    mejor_valoradas_limpias = []
    recomendacion_semanal = {}

    # 🛡️ BLOQUE INTELIGENTE: RECOMENDACIÓN ALEATORIA Y NUEVA
    try:
        # 1. Traemos los IDs de las series que ya tienes en tu Base de Datos (las que ya conoces o viste)
        # Recogemos los id_tmdb de tu modelo local para saber cuáles excluir
        ids_locales_vistas = list(
            Serie.objects.exclude(id_tmdb__isnull=True)
            .exclude(id_tmdb=0)
            .values_list("id_tmdb", flat=True)
        )

        # 2. Consultamos una lista grande de series animadas populares en TMDB para "descubrir"
        url_descubrir_candidatas = f"https://api.themoviedb.org/3/discover/tv?api_key={api_key}&language=es-MX&sort_by=popularity.desc&with_genres=16&with_type=2|4&page=1"
        res_descubrir = requests.get(url_descubrir_candidatas, timeout=2.5).json()

        candidatas_nuevas = []

        # 3. Filtramos: Solo guardamos las que NO están en tus países de anime Y NO están en tus series vistas
        for s in res_descubrir.get("results", []):
            id_candidata = s.get("id")
            if not any(p in s.get("origin_country", []) for p in paises_anime):
                if id_candidata not in ids_locales_vistas:
                    candidatas_nuevas.append(s)

        # 4. ¡La magia de la aleatoriedad!
        # Si encontramos series nuevas que no has visto, elegimos una al azar usando random.choice
        if candidatas_nuevas:
            # Para que cambie según la semana del año de forma estable pero aleatoria:
            # Usamos la semana_actual como 'semilla' para que sea la misma toda la semana, pero cambie el próximo lunes
            random.seed(semana_actual)
            serie_elegida = random.choice(candidatas_nuevas)
            random.seed()  # Limpiamos la semilla para no afectar otros randoms del proyecto

            # Pedimos los detalles completos de esa serie elegida al azar para traer sus géneros y temporadas
            url_detalle_elegida = f"https://api.themoviedb.org/3/tv/{serie_elegida.get('id')}?api_key={api_key}&language=es-MX"
            res_det = requests.get(url_detalle_elegida, timeout=2.5).json()

            recomendacion_semanal = {
                "id": res_det.get("id"),
                "titulo": res_det.get("name"),
                "sinopsis": res_det.get(
                    "overview", "No hay sinopsis disponible en este momento."
                )[:280]
                + "...",
                "poster": res_det.get("poster_path"),
                "banner": res_det.get("backdrop_path"),
                "temporadas": res_det.get("number_of_seasons", 1),
                "generos": " • ".join(
                    [g["name"] for g in res_det.get("genres", [])[:4]]
                ),
            }

    except Exception as e:
        print(f"Error procesando la recomendación aleatoria y nueva: {e}")

    # 🛡️ BLOQUE INDEPENDIENTE PARA LAS LISTAS DEL CATÁLOGO
    try:
        # 2. Procesar Tendencias
        res_p = requests.get(url_populares, timeout=2.5).json()
        for s in res_p.get("results", []):
            if not any(p in s.get("origin_country", []) for p in paises_anime):
                g_nombres = [
                    generos_map.get(gid)
                    for gid in s.get("genre_ids", [])
                    if gid in generos_map
                ]
                tendencias_limpias.append(
                    {
                        "id": s.get("id"),
                        "titulo": s.get("name"),
                        "poster_path": s.get("poster_path"),
                        "nota": s.get("vote_average", 0.0),
                        "fecha_estreno": (
                            s.get("first_air_date", "S/D")[:4]
                            if s.get("first_air_date")
                            else "N/A"
                        ),
                        "generos": (
                            " • ".join(g_nombres[:3]) if g_nombres else "Animation"
                        ),
                        "total_capitulos": "Info en detalle",
                    }
                )

        # 3. Procesar Novedades
        res_n = requests.get(url_novedades, timeout=2.5).json()
        for s in res_n.get("results", []):
            if not any(p in s.get("origin_country", []) for p in paises_anime):
                g_nombres = [
                    generos_map.get(gid)
                    for gid in s.get("genre_ids", [])
                    if gid in generos_map
                ]
                novedades_limpias.append(
                    {
                        "id": s.get("id"),
                        "titulo": s.get("name"),
                        "poster_path": s.get("poster_path"),
                        "nota": s.get("vote_average", 0.0),
                        "fecha_estreno": (
                            s.get("first_air_date", "S/D")[:4]
                            if s.get("first_air_date")
                            else "N/A"
                        ),
                        "generos": (
                            " • ".join(g_nombres[:3]) if g_nombres else "Animation"
                        ),
                        "total_capitulos": "Info en detalle",
                    }
                )

        # 4. Procesar Mejor Valoradas
        res_m = requests.get(url_mejor_valoradas, timeout=2.5).json()
        for s in res_m.get("results", []):
            if not any(p in s.get("origin_country", []) for p in paises_anime):
                g_nombres = [
                    generos_map.get(gid)
                    for gid in s.get("genre_ids", [])
                    if gid in generos_map
                ]
                mejor_valoradas_limpias.append(
                    {
                        "id": s.get("id"),
                        "titulo": s.get("name"),
                        "poster_path": s.get("poster_path"),
                        "nota": s.get("vote_average", 0.0),
                        "fecha_estreno": (
                            s.get("first_air_date", "S/D")[:4]
                            if s.get("first_air_date")
                            else "N/A"
                        ),
                        "generos": (
                            " • ".join(g_nombres[:3]) if g_nombres else "Animation"
                        ),
                        "total_capitulos": "Info en detalle",
                    }
                )
    except Exception as e:
        print(f"Error procesando listas del catálogo: {e}")

    recomendacion_para = (
        recomendacion_semanal if request.user.is_authenticated else None
    )

    contexto = {
        "recomendacion": recomendacion_para,
        "tendencias": tendencias_limpias[:8],
        "novedades": novedades_limpias[:8],
        "mejor_valoradas": mejor_valoradas_limpias[:8],
        "mis_series": [
            {
                "id": s.id,
                "titulo": s.titulo,
                "poster_path": s.poster_path,
                "nota": s.calificacion,
                "generos": s.generos if s.generos else "Animation",
                "fecha_estreno": s.fecha_estreno if s.fecha_estreno else "",
            }
            for s in Serie.objects.all()
        ],
    }

    if request.user.is_authenticated:
        contexto["notificaciones_count"] = 0

    return render(request, "series/index.html", contexto)


# 6. Búsqueda de series
def buscar_series(request):
    query = request.GET.get("q", "")
    resultados_animados = []

    if query:
        api_key = "ea735303fe1aa8a04e298b1f9c130e6c"
        url = f"https://api.themoviedb.org/3/search/tv?api_key={api_key}&query={query}&language=en-US"
        try:
            datos = requests.get(url, timeout=3.0).json()
            for resultado in datos.get("results", []):
                if 16 in resultado.get("genre_ids", []) and "JP" not in resultado.get(
                    "origin_country", []
                ):
                    resultados_animados.append(resultado)
        except Exception:
            pass

    return render(
        request,
        "series/resultados_busqueda.html",
        {"resultados": resultados_animados, "busqueda": query},
    )


# ============ VISTAS DE AUTENTICACIÓN Y PERFIL ============


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
    return render(
        request,
        "series/ver_perfil.html",
        {
            "usuario": usuario,
            "perfil": usuario.perfil,
            "series": Serie.objects.all(),
            "es_propietario": (
                request.user == usuario if request.user.is_authenticated else False
            ),
        },
    )
