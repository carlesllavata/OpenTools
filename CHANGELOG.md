# Diario de cambios

Lo que va añadiendo cada versión de Open3DS, de la más reciente a la más antigua.

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
