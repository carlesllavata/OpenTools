# Diario de cambios

Lo que va añadiendo cada versión de Open3DS, de la más reciente a la más antigua.

## En desarrollo

### 9 de noviembre de 2026

- **Ignite desaparece; lo suyo se reparte.** Repetía lo que ya hace el Object Clipboard
  (mismas ranuras, mismo copiar y pegar), así que solo se quedan las dos cosas que tenía
  propias:
  - **Opciones de pegado en el Object Clipboard.** Debajo del destino aparecen las
    opciones del modo elegido: en **Modifiers**, pegar como instancias; en **Keys**,
    mantener la posición de cada objeto en un frame y desplazar las claves en el tiempo.
  - **Nueva herramienta: Random Replace** (categoría Modeling). Sustituye los objetos
    seleccionados (cajas, marcadores…) por varias fuentes elegidas al azar según su peso,
    conservando posición, giro, escala y capa. Se deshace con un solo Ctrl+Z. Si tenías
    Ignite en una barra o con un atajo, ahora abre Random Replace.
- **Menú Open3DS en la barra de menús de 3ds Max.** Muestra u oculta el panel (si lo
  cierras con la X, desde aquí vuelve), abre la paleta de comandos y tiene todas las
  herramientas ordenadas por categoría.

## 0.4.0 — 8 de noviembre de 2026

Ocho herramientas nuevas para el día a día, un panel que se ordena a tu gusto y dos
cierres de 3ds Max corregidos.

- **Filtrar por varias categorías.** Los botones de categoría bajo el buscador ahora se
  marcan y desmarcan uno a uno, y el panel muestra solo las categorías elegidas (por
  ejemplo, Materials y Scene a la vez). **All** vuelve a mostrarlo todo. El filtro se
  recuerda entre sesiones.
- **Materials es una categoría más**, con su propio botón.
- Los puntos de color de las categorías se ven también con el botón activo.
- **Ordenar las categorías a tu gusto.** Arrastra un botón de categoría encima de otro
  para cambiar el orden de los botones y de las secciones, o usa el clic derecho (mover
  al principio, a la izquierda, a la derecha, al final). Por defecto van en orden
  alfabético, y "Default order" vuelve a él.
- Las cabeceras de las secciones muestran el nombre tal cual (en negrita, ya no en
  mayúsculas), igual que los botones de arriba.
- **Corregido el parpadeo.** Al mostrar u ocultar categorías ya no aparece un instante
  una ventana vacía.
- **Nueva herramienta: Random Select** (categoría Selection). Eliges un porcentaje y deja
  seleccionada esa parte de la selección actual, al azar: de 10 objetos al 30 % quedan 3.
  Si vuelves a pulsar, sortea de nuevo entre los 10 originales, sin tener que volver a
  seleccionarlos. Los grupos cerrados cuentan como un solo objeto (entran o salen
  enteros), siempre queda al menos uno y se deshace con un solo Ctrl+Z. El porcentaje se
  recuerda entre sesiones.
- **Nueva herramienta: Random Wire Color** (categoría Scene). Con un clic, cada objeto
  seleccionado recibe un color de objeto distinto (el color que aparece arriba a la derecha
  en el panel Modify), ideal para separar objetos con máscaras por color como Mask ID. Los
  colores se reparten para que nunca salgan dos casi iguales ni grises, negros o blancos, y
  cada clic da una combinación nueva. Se deshace con un solo Ctrl+Z.
- **Nueva herramienta: Turn to Instance** (categoría Modeling), basada en el script de
  Miled Rizk e incluida con su permiso. Seleccionas los objetos, la lanzas y haces clic en
  el objeto origen: cada uno pasa a ser una instancia completa del origen (geometría,
  modificadores, material y nombre numerado) sin moverse de su sitio, y conserva su
  jerarquía y su capa. Funciona con geometría, splines, cámaras y luces (las de tipo
  distinto se saltan), sin estropear el FOV de las cámaras con target. Se deshace con un
  solo Ctrl+Z.
- **Nuevos botones: Copy / Paste Material + UVW** (categoría Materials), basados en CPM
  Lite de Aleksey Sheremetov e incluidos con su permiso. **Copy Material + UVW** guarda el
  material de un objeto y sus modificadores de mapeado (UVW Map, Unwrap UVW, UVW Xform…);
  **Paste Material** lo asigna a la selección; **Paste Material + UVW** además cambia el
  mapeado de los objetos por el copiado, sin tocar el resto de su pila. Las versiones
  **Copy** pegan una copia independiente del material ("Copy-…") y la dejan elegida en la
  barra de materiales, lista para editar. Todo se deshace con un solo Ctrl+Z.
- **Sección Materials ordenada.** Los botones de Materials van debajo de la barra de
  materiales, en una sola sección que se pliega entera.
- **Nueva herramienta: Clean DWG** (categoría Scene), basada en el script de Juan Camilo
  Alcaraz (Alzarac) e incluida con su permiso. Para el dibujo importado de AutoCAD: escribe
  un nombre y pulsa Start. Abre los grupos, aplana todas las líneas a Z = 0 y borra lo que
  no son líneas; lo pasa todo a una capa nueva con ese nombre, conservando los colores; lo
  agrupa; y borra las capas del DWG que quedan vacías. Cada paso se puede desactivar. Tus
  capas vacías de plantilla no se tocan, y todo se deshace con un solo Ctrl+Z, capas
  incluidas.
- **Nuevas herramientas: 3-Point Rotate y 3-Point Scale** (categoría Modeling), basadas en
  los scripts de Sergo Pogosyan e incluidas con su permiso. Como el girar y el escalar por
  referencia de AutoCAD: tres clics con snaps (punto base, un punto del objeto y dónde debe
  quedar) y listo. El giro siempre va hacia el lado correcto, sin casilla "Flip", y
  funciona en planta y en alzado. Se deshacen con un solo Ctrl+Z.
- **Corregido: Turn to Instance** fallaba la primera vez que se usaba en una sesión de
  3ds Max ("Unknown property … in undefined").
- **Corregido: cierre de 3ds Max al deshacer** después de que Forensic borrara capas
  vacías. Ahora ese borrado también se puede deshacer.

## 0.3.0 — 8 de noviembre de 2026

Una sola estética para toda la app, que sigue los colores de 3ds Max.

- **Tema común.** El panel y todas las ventanas (Forensic, Ignite, Object Clipboard, los
  gestores de assets, proxies y XRefs, Attach / Detach y la paleta de comandos) comparten
  el mismo aspecto. Fondos, textos y bordes salen de la paleta de 3ds Max: si cambias el
  tema de Max, Open3DS cambia con él. Solo el naranja de acento y los colores de estado
  son fijos.
- **Panel rediseñado.** Buscador con botones de recargar y opciones; filtros de categoría
  como botones con su punto de color; secciones plegables con barra de color, nombre en
  mayúsculas y número de herramientas; y las herramientas como botones horizontales con
  icono pequeño y nombre, repartidos en columnas que se adaptan al ancho del panel.
- **Sección Materials.** La barra de materiales deja de estar arriba del todo y pasa a
  ser una sección propia debajo de Clipboard (desplegable, cuentagotas, aplicar y
  seleccionar). Se puede ocultar desde el menú `⋯`.
- **Botones al estilo Forensic** en todas partes, y casillas, desplegables, selectores
  numéricos y pestañas con el mismo estilo.
- **Limpieza interna.** Fuera código repetido y sin uso; las ventanas de herramienta
  recuerdan su tamaño y piden confirmación de una sola forma común.

## 0.2.0 — 7 de noviembre de 2026

La colección de herramientas toma forma.

- **Forensic**: la escena entera en tarjetas (render, estados de objetos, geometría,
  limpieza, animación, materiales y modificadores, referencias, salud de la escena) con
  botones para seleccionar y reparar en un clic, además de la lista de modificadores y
  los datos del archivo.
- **Ignite**: copiar y pegar objetos, pilas de modificadores, materiales y claves de
  animación entre escenas, y reemplazar objetos por varias fuentes al azar por peso.
- **Object Clipboard**: 8 ranuras con miniaturas, en local o en carpetas de red
  compartidas; pegar en el sitio, en el cursor o como sello; bloqueo de ranuras y HUD en
  el visor.
- **Asset Manager**: todos los archivos externos de la escena, con reenlace de los que
  faltan, limpieza de rutas y recopilación en una carpeta.
- **Proxy Display Manager** y **XRef Display Manager**.
- **Attach Objects**, **Detach Elements** y **Reset XForm + Collapse**.
- **Barra de materiales** en el panel, al estilo de la lista de capas de AutoCAD.

## 0.1.0 — 6 de noviembre de 2026

Primera versión: la base del hub.

- Un solo paquete para instalar en 3ds Max 2025 o posterior.
- Panel acoplable con las herramientas por categorías, buscador y favoritos.
- Paleta de comandos y macros para asignar atajos de teclado a cada herramienta.
- Cada herramienta es una carpeta con su `tool.json`; si una falla, las demás siguen
  funcionando.
