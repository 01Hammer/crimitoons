# 📝 TOODO · Crimitoons

La lista de pendientes del proyecto: lo que falta construir, lo que falta terminar y lo que se quiere añadir a futuro.

> 🚧 Crimitoons está **en desarrollo**. Esta lista cambia constantemente: se tachan cosas, aparecen otras nuevas y algunas decisiones todavía están abiertas.

**Cómo leerla**

- `[ ]` pendiente · `[x]` terminado
- 🆕 **Por hacer**: vistas y funciones que aún no existen.
- 🔧 **Por terminar**: cosas que existen pero están a medias o con errores.
- 💭 **Posibles adiciones**: ideas ambiciosas que no están en el plan actual.
- ❓ Marca una decisión que hay que tomar antes de seguir.

---

## 🆕 Por hacer

Lo que todavía no existe y es necesario.

### 👥 Amigos
- [ ] Página o modal con la lista de amigos.
- [ ] Vista del perfil de un amigo. Es casi igual a la de "Mi perfil", con ajustes (por ejemplo, sin opciones de edición).

### 🏅 Insignias
- [ ] Diseñar las plantillas de las insignias. La idea ya existe en la página, pero todavía no se ha hecho nada visual con ellas.

### 💬 Página dedicada a los foros
- [ ] Crear una vista propia para los foros. Como se espera que crezcan mucho, merecen su propio espacio.

### 📖 Historias
- [ ] Crear un espacio dedicado para las historias: textos larguísimos con título e imágenes, pensados para fanfics y relatos.
- [ ] ❓ Definir cómo funcionan por dentro (longitud, formato, capítulos, edición) y repasar la idea original antes de empezar.

---

## 🔧 Por terminar

Lo que ya existe, pero hay que pulirlo hasta dejarlo perfecto.

### 🧭 Barra de navegación (navbar)
- [ ] Que sea completamente funcional y se vea bien en **todas** las vistas. Todavía falla en algunos casos.

### 🏠 Inicio (index / landing)
Es la vista más avanzada, pero le faltan detalles.
- [ ] **Zona de foros**: hoy muestra los últimos foros de forma visual, pero son estáticos. Hay que conectarla con los foros reales.
- [ ] **"Mis series"**: debería mostrar las últimas series que entraron a tus listas. Ahora muestra las últimas series cuyo detalle visitaste.

### 🔔 Notificaciones
- [ ] El botón existe, pero no registra nada. Falta:
  - [ ] Guardar las notificaciones.
  - [ ] Una mini interfaz para verlas.
  - [ ] Avisos de likes.
  - [ ] Avisos de comentarios.
  - [ ] Avisos de menciones.
  - [ ] Otras novedades de la cuenta.

### 🔍 Explorar
- [ ] **Filtros**: la búsqueda funciona, pero los filtros no. Hay que dejarlos funcionando.
- [ ] **Colores de estado**: los colores que reflejan el estado de cada serie fallan a veces. Corregirlos.
- [ ] Seguir revisando el catálogo. Ya se excluyó gran parte del anime, las series chinas y coreanas y las de personas reales, pero probablemente quedan rezagadas.

### 🗣️ Comunidad
Una de las páginas más cargadas.

**Filtros**
- [ ] Hacer funcionar los filtros para ver solo: publicaciones, actualizaciones de estado de series, amigos o foros.
- [ ] ❓ Decidir cuáles filtros se quedan y cuáles no.

**Caja de publicar**
- [ ] Vista previa del contenido multimedia (imagen y video).
- [ ] Dar funcionamiento a los botones: **foro**, **serie**, **encuesta** e **historia**.
- [ ] Diseñar la apariencia de cada uno de los 4 modos. La caja se transforma para darle a cada uno el espacio que necesita.

**Publicaciones**
- [ ] Rediseñar las tarjetas de cada tipo (automáticas y manuales). Hoy son simples y desordenadas, y se hicieron con prisa.
- [ ] Corregir los botones que fallan o se comportan mal.

**Foros calientes** (columna derecha)
- [ ] Ya muestra los foros nuevos, pero es una versión muy temprana.
- [ ] ❓ Decidir si se queda. Si se queda, definir qué cuenta como "caliente" (populares, recientes o ambos).

### 👤 Mi perfil
Una vista compleja y pesada que todavía está lejos de estar lista.
- [ ] Mostrar actualizaciones de estadísticas.
- [ ] Mostrar actualizaciones de estado.
- [ ] Mostrar últimas series y favoritas.
- [ ] Completar todas las pestañas con los datos del usuario.

### ⚙️ Configuración
- [ ] Hoy solo permite cambiar la foto de perfil y el banner.
- [ ] Hacer funcionar el **"tablero"**.
- [ ] Añadir los ajustes típicos que todavía no existen.

---

## 💭 Posibles adiciones

Ideas que se salen de los planes actuales. Son ambiciosas y llegarían al final.

### 🤖 Asistente de Crimitoons
- [ ] Un asistente que:
  - [ ] Recomienda series cuando se lo pides.
  - [ ] Tiene en cuenta lo que hay en tus listas.
  - [ ] Conversa sobre lo que estás viendo en pantalla.

---

## 🛠️ Mantenimiento técnico

Cosas de fondo que ayudan a que el proyecto sea sólido y seguro.
- [ ] Mover las claves y secretos del proyecto a variables de entorno.
- [ ] Revisar la configuración para producción (modo de depuración y claves por defecto).
- [ ] Elegir una licencia para el repositorio.
- [ ] Mantener la descripción del repositorio al día con la tecnología real.
- [ ] Ordenar las vistas en módulos más pequeños, por tema.
