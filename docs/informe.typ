// ============================================================================
//  DATOS QUE DEBEN COMPLETAR (todo lo marcado en rojo en el PDF sale de aquí)
// ============================================================================
#let falta(t) = text(fill: rgb("#c0392b"), weight: "bold")[⟦#t⟧]

#let integrantes = (
  // (nombre, qué hizo)
  ("[Nombre 1]", "[p. ej.: entrenamiento del modelo y análisis técnico]"),
  ("[Nombre 2]", "[p. ej.: sistema.py, base de datos y repositorio]"),
  ("[Nombre 3]", "[p. ej.: dataset, fotos propias, informe y video]"),
)
#let empresa = "[Nombre de la empresa]"
#let sector = "[Sector: construcción / seguridad industrial / …]"
#let uso = "[quién usaría el sistema, dónde se instala la cámara]"
#let problema = "[qué le cuesta hoy a la empresa no controlar el EPP: accidentes, multas, tiempo del inspector]"
#let indicador = "[número: p. ej. «detectar ≥ 90 % de las personas sin casco o chaleco en zona»; línea base: __ revisiones manuales/día; meta: __]"
#let n_fotos_propias = "[N]"
#let enlace_repo = "[enlace de GitHub]"
#let enlace_dataset = "https://huggingface.co/buckets/CJ305/proyecto-final-vision-artificial-epp-storage"
#let enlace_video = "[enlace de YouTube / Drive]"
#let cita_dataset = "[Autor]. «Safety Helmet Reflective Jacket». Kaggle. [URL, fecha de consulta]"

// ============================================================================
#set document(title: "Proyecto final Visión Artificial – Detector de EPP en obra")
#set page(paper: "a4", margin: (x: 2.1cm, y: 2.0cm), numbering: "1",
  footer: context [#set text(8pt, fill: gray); Detector de EPP en obra · Visión Artificial · Universidad de La Guajira #h(1fr) #counter(page).display()])
#set text(font: ("Inter", "DM Sans", "FreeSans"), size: 9.3pt, lang: "es")
#set par(justify: true, leading: 0.62em)
#set heading(numbering: "1.")
#show heading.where(level: 1): it => block(above: 1.1em, below: 0.6em, text(14pt, weight: "bold", fill: rgb("#1f3a5f"), it))
#show heading.where(level: 2): it => block(above: 0.9em, below: 0.4em, text(11pt, weight: "bold", fill: rgb("#1f3a5f"), it))
#show raw: set text(font: ("Inconsolata", "DejaVu Sans Mono"), size: 9pt)
#show figure.caption: set text(8.5pt)
#set table(stroke: 0.5pt + luma(180), inset: 5pt)
#show table.cell.where(y: 0): set text(weight: "bold")
#let tabla(..a) = block(breakable: false, table(fill: (_, y) => if y == 0 { rgb("#e8eef6") }, ..a))

// ------------------------------------------------------------------ portada
#align(center)[
  #v(0.5cm)
  #text(9pt, fill: gray)[Visión Artificial · Ingeniería de Sistemas · Universidad de La Guajira · Docente: Eduardo Sierra Fragozo]
  #v(0.3cm)
  #text(21pt, weight: "bold", fill: rgb("#1f3a5f"))[Detector de elementos de protección personal en obra]
  #v(0.1cm)
  #text(12pt)[Proyecto final – Proyecto 3 · Casco y chaleco con alerta por zona]
  #v(0.2cm)
  #text(10pt)[#integrantes.map(i => i.at(0)).join(" · ")]
  #v(0.1cm)
  #text(9pt, fill: gray)[24 de noviembre de 2026]
]
#v(0.2cm)
#block(fill: rgb("#eef3f9"), inset: 9pt, radius: 4pt, width: 100%)[
  *Resumen.* Construimos un sistema que detecta personas, cascos y chalecos con YOLOv8n, asocia el equipo a cada persona y
  genera una alerta cuando alguien sin casco o sin chaleco permanece 15 cuadros seguidos dentro de un polígono marcado. Cada alerta
  se guarda en SQLite con zona, hora, falta, confianza y captura. En 1 050 imágenes de prueba el modelo logra mAP50 de 0.940
  y la decisión «incumple» por persona alcanza precisión 0.94 y recall 0.89. El sistema corre a ~137 FPS en GPU y ~37 FPS en CPU.
  Aun así, no detecta al 14 % de las personas del conjunto de prueba, por lo que describimos qué falta para un uso real.
  *Repositorio:* #enlace_repo · *Video:* #enlace_video · *Dataset:* #enlace_dataset
]

// ------------------------------------------------------------------ 1
= Ficha del cliente
#tabla(columns: (3.2cm, 1fr),
  [Concepto], [Descripción],
  [Empresa], [#falta(empresa)],
  [Sector], [#falta(sector)],
  [Uso del sistema], [#falta(uso)],
  [Quién lo opera], [#falta("persona encargada de seguridad / residente de obra")],
)
#text(8.5pt, fill: gray)[Si la empresa es real, no se publican datos privados de ella ni de sus empleados sin autorización.]

= Problema de negocio e indicador de éxito
*Problema.* #falta(problema) Un inspector no puede mirar todas las zonas de riesgo todo el tiempo; el sistema vigila de forma
continua y deja evidencia (hora, zona y foto) de cada incumplimiento.

*Indicador de éxito.* #falta(indicador)

*Requisitos del cliente.* (1) Alertar solo si la persona sin equipo está dentro de la zona marcada, para no molestar con falsas alarmas
fuera de ella. (2) Guardar cada evento con evidencia consultable. (3) Funcionar con una cámara fija y un computador común.
(4) Poder redefinir la zona sin tocar el código.
*Medida técnica propia* (con datos de prueba): de las personas detectadas, el sistema identifica el 89 % de los incumplimientos
reales y el 94 % de sus alertas son correctas (sección 6).

// ------------------------------------------------------------------ 3
= Datos
*Origen.* Dataset público de Kaggle: #cita_dataset, más #falta(n_fotos_propias + " fotos propias") tomadas por el grupo.
El conjunto final tiene *10 500 imágenes* y *48 597 cajas*: casco 18 528, chaleco 14 516 y persona 15 553.
*División 70/20/10:* 7 350 entrenamiento, 2 100 validación y 1 050 prueba (se movieron 525 imágenes de prueba a validación con `mover.py`, semilla 42).

*Etiquetado.* El dataset original traía solo casco y chaleco. La clase *persona* se pre-llenó automáticamente con YOLOv8n preentrenado en COCO
(clase 0, confianza ≥ 0.4, `prellenar.py`) y se revisó por muestra. `limpiar.py` eliminó etiquetas con clases ajenas y `verificar.py` comprobó
que cada imagen tuviera su etiqueta, que las cajas estuvieran entre 0 y 1 y que los identificadores de clase existieran en `data.yaml`.
*Limitación:* las etiquetas de persona son automáticas, así que heredan los errores de COCO (personas cortadas, muy pequeñas o ilustraciones).

// ------------------------------------------------------------------ 4
= Modelo y base de datos
*Modelo.* YOLOv8n (3 138 489 parámetros, 8.8 GFLOPs a 640 × 640) con pesos preentrenados en COCO, afinado 60 épocas:
imagen 640, lote 8, optimizador automático, tasa de aprendizaje inicial 0.01, aumento mosaico 1.0, ≈ 75 min de entrenamiento.
Clases: 0 casco, 1 chaleco, 2 persona.

*Base de datos (SQLite, `db/schema.sql`).*
#tabla(columns: (3.2cm, 2.2cm, 1fr),
  [Columna], [Tipo], [Contenido],
  [`id`], [INTEGER PK], [Identificador autoincremental],
  [`momento`], [TEXT], [Fecha y hora ISO 8601 del evento],
  [`zona`], [TEXT], [Nombre de la zona vigilada (índice con `momento`)],
  [`falta_casco`, `falta_chaleco`], [INTEGER], [1 si faltaba cada equipo],
  [`confianza`], [REAL], [Confianza de la detección de la persona],
  [`ruta_captura`], [TEXT], [Imagen con la alerta dibujada],
)

// ------------------------------------------------------------------ 5
= Metodología
+ *Detección.* Cada cuadro pasa por YOLO con umbral de confianza 0.4 y devuelve cajas de casco, chaleco y persona.
+ *Asociación persona–equipo.* Un casco pertenece a la persona si su centro cae dentro de la caja de la persona y en su *tercio superior*;
  un chaleco, si su centro cae entre el *30 % y el 75 % de la altura*. Si no hay casco (o chaleco) asociado, se marca la falta.
+ *Zona restringida.* El usuario marca un polígono con 4 clics (se guarda en `zona.json`). La persona está dentro si el punto central
  de la base de su caja (los pies) cae en el polígono (`cv2.pointPolygonTest`).
+ *Alerta.* Solo cuenta una persona dentro de la zona con falta. La alerta salta cuando la falta se mantiene *15 cuadros seguidos*
  (0.6 s a 25 FPS), lo que filtra parpadeos de la detección; genera un solo evento por episodio.
+ *Guardado.* Se escribe la captura con las marcas dibujadas y una fila en `eventos`; `reporte.py` agrupa los incumplimientos por zona y por hora.

#figure(image("/demo/captura_sistema_alerta.jpg", width: 6.2cm),
  caption: [Alerta activa: persona en rojo con «SIN CHALECO», zona azul, barra de estado y banner inferior.])

= Interfaz web y despliegue
Además del procesamiento de video (`sistema.py`), el sistema ofrece una *app web* (Flask, `src/app.py`) para que el personal en obra reporte con el celular:
abre una página, toma una foto o graba un video, el navegador lee el *GPS* en ese momento y el servidor aplica el mismo modelo y la misma regla de asociación.
Si alguien incumple, se guarda un evento con zona, hora, falta, confianza, captura y *latitud, longitud y precisión del GPS* en la tabla `eventos`.
El *panel* (`/panel`) consulta la base de datos y muestra los eventos en un mapa, una tabla con enlace a la ubicación y el reporte de incumplimientos por zona y hora (reto extra).
En una foto se evalúan todas las personas del encuadre y se asume que se toma dentro de la zona vigilada; en un video se analiza medio segundo sí y medio no, y se dispara tras 3 muestras seguidas con falta.

*Despliegue.* El sistema corre fuera de Colab como *API* (`/api/analizar`, `/api/eventos`) empaquetada en un *contenedor Docker* (`Dockerfile`: PyTorch para CPU, gunicorn, modelo incluido).
El acceso está protegido con usuario y contraseña, y puede abrirse desde cualquier red mediante un túnel HTTPS de Cloudflare, lo que permite usar cámara y GPS desde el celular.
No lo desplegamos en un servicio de nube de pago; el mismo `Dockerfile` serviría para hacerlo. *Privacidad:* las capturas muestran personas y ubicaciones, por lo que su uso requiere autorización de la empresa.

// ------------------------------------------------------------------ 6
= Resultados
*Detección en el conjunto de prueba (1 050 imágenes).*
#tabla(columns: (3cm, 1fr, 1fr, 1fr, 1fr),
  [Clase], [mAP50], [mAP50-95], [Precisión], [Recall],
  [Casco], [0.955], [0.738], [0.934], [0.904],
  [Chaleco], [0.951], [0.751], [0.891], [0.897],
  [Persona], [0.914], [0.754], [0.894], [0.826],
  [*Global*], [*0.940*], [*0.748*], [*0.906*], [*0.876*],
)
*Decisión del sistema por persona* (conf 0.4, IoU ≥ 0.5 con la persona etiquetada): de 1 617 personas, el modelo detecta 1 393 (86 %).
Entre ellas, la clasificación «incumple / cumple» tiene precisión 0.942, recall 0.888 y F1 0.914 (663 aciertos, 41 falsas alarmas, 84 incumplimientos perdidos, 605 cumplimientos correctos).
Los datos salen de `scripts/analisis.py` (`resultados/analisis/analisis.json`).

#figure(image("/resultados/results.png", width: 100%),
  caption: [Curvas de entrenamiento (`results.png`): las pérdidas bajan y mAP50 sube de 0.805 (época 1) a 0.950 (época 60) en validación.])
#grid(columns: (1fr, 1fr), gutter: 8pt,
  figure(image("/resultados/confusion_matrix_normalized.png", width: 100%), caption: [Matriz de confusión normalizada (prueba).]),
  figure(image("/resultados/BoxPR_curve.png", width: 100%), caption: [Curva precisión–recall por clase.]),
)

// ------------------------------------------------------------------ 7
= Análisis técnico
== A. Por qué funciona el modelo
*De la imagen a la caja.* (1) OpenCV lee el cuadro como matriz de enteros 0–255 en orden BGR. (2) Se redimensiona a 640 × 640 conservando la proporción (rellenando con gris),
se pasa a RGB y se divide entre 255 para que los valores queden entre 0 y 1. (3) La red aplica capas convolucionales con paso 2 que reducen el tamaño
(640 → 320 → 160 → 80 → 40 → 20) y aumentan los canales: al principio detectan bordes y texturas; más adentro, formas como un casco o una franja reflectiva.
(4) Una etapa intermedia (PAN-FPN) mezcla los mapas de varias escalas para que objetos pequeños y grandes se vean bien.
(5) La cabeza produce, en cada celda de las tres mallas (80×80, 40×40 y 20×20), una caja y una puntuación por clase.
(6) Se descartan las cajas con confianza menor a 0.4 y la supresión de no máximos (NMS) elimina duplicados con IoU alto, dejando una caja por objeto.

*Qué aprende en el entrenamiento.* Los pesos de los filtros arrancan con los de COCO y se ajustan para reducir una pérdida compuesta
(error de posición de la caja con CIoU, error de clase y error de distribución de bordes). En cada época, la red compara su predicción con las etiquetas, calcula el error y corrige los pesos
con retropropagación. El aumento por mosaico (cuatro imágenes en una) obliga a reconocer objetos en contextos y tamaños distintos.

*Ventaja del modelo preentrenado.* Los filtros de bajo nivel (bordes, colores, texturas) ya estaban aprendidos con cientos de miles de imágenes de COCO, así que solo hubo que enseñar «qué es un casco y un chaleco».
Se nota en los datos: en la época 1 ya había mAP50 de 0.805, y sobre 7 350 imágenes llegó a 0.950; entrenar desde cero con tan pocas imágenes necesitaría muchas más épocas y datos.

== B. Lo aprendido en el semestre
#tabla(columns: (3.3cm, 1fr, 3.6cm),
  [Concepto del curso], [Dónde aparece en el sistema], [Programado por nosotros],
  [Convoluciones], [Es la operación central de toda la red YOLO (cientos de miles de filtros 3×3 y 1×1).], [No (viene en YOLO)],
  [Filtros (suavizado, bordes)], [Las primeras capas aprenden filtros tipo borde; en C aplicamos a mano un promedio, Sobel y Laplaciano.], [Solo en el experimento C],
  [Umbralización], [Umbral de confianza 0.4, umbral de IoU de NMS 0.7, umbral de 15 cuadros para alertar.], [Sí (conf y cuadros)],
  [IoU], [NMS y evaluación (acierto si IoU ≥ 0.5). Nuestra asociación persona–equipo usa el centro dentro de la caja, no IoU.], [Evaluación sí; NMS no],
  [Modelo de cámara], [Cámara fija: el tamaño aparente cae con la distancia (efecto medido abajo). No calibramos ni usamos homografía; la zona es un polígono en píxeles.], [Parcial (zona en píxeles)],
  [Normalización / color], [Conversión BGR → RGB y división entre 255 antes de la red.], [No (la hace Ultralytics)],
  [Geometría], [Prueba punto-en-polígono con la base de la caja de la persona.], [Sí],
)
*Concepto usado sin programarlo:* las convoluciones, junto con la normalización por lotes, la activación SiLU y el NMS: forman la red y no escribimos ninguna.

*Efecto de la distancia.* El recall de persona baja cuanto más lejos está (tamaño de la persona respecto a la imagen):
#tabla(columns: (4cm, 2cm, 1fr), [Tamaño de la persona], [Personas], [Recall (conf 0.4)],
  [Lejos (< 15 % del alto)], [82], [0.61], [Media (15–40 %)], [354], [0.80], [Cerca (> 40 %)], [1 181], [0.90])
Una persona lejana ocupa pocos píxeles; tras redimensionar a 640 su casco mide apenas unos pocos píxeles y sus rasgos se pierden.

*Efecto de la iluminación.* Multiplicamos el brillo de 300 imágenes de prueba (factor 1.0 = original) y medimos el recall a conf 0.4:
#tabla(columns: (3cm, 1fr, 1fr, 1fr, 1fr),
  [Brillo], [Casco], [Chaleco], [Persona], [F1 global],
  [× 0.25], [0.891], [0.862], [0.784], [0.889],
  [× 0.5], [0.925], [0.900], [0.807], [0.899],
  [× 1.0 (original)], [0.932], [0.906], [0.818], [0.900],
  [× 1.5], [0.891], [0.873], [0.779], [0.883],
  [× 2.0], [0.800], [0.814], [0.672], [0.835],
)
La sobreexposición (× 2) daña más que la oscuridad moderada: satura los colores que distinguen el equipo. En las imágenes naturales, agrupadas por brillo medio,
el recall de persona fue 0.87 (oscuras), 0.86 (medias) y 0.84 (claras), sin una diferencia grande, probablemente porque el entrenamiento ya incluye escenas de noche y de día.
#figure(image("/docs/figuras/fig_distancia_iluminacion.png", width: 11cm), caption: [Recall de persona según tamaño (distancia) y brillo natural.])

== C. Las operaciones aritméticas
El sistema ejecuta: *convoluciones* (sumas de productos entre un filtro y un parche; ≈ 4.4 mil millones de multiplicaciones-acumulaciones por imagen, pues 8.8 GFLOPs ≈ 2 × MACs),
*normalización por lotes* (restar media y dividir por desviación), *activación SiLU* (x multiplicada por la sigmoide), *productos punto* en las capas finales,
*promedios y máximos* (agrupaciones y NMS), *umbrales y comparaciones* (confianza, IoU, polígono) y *normalización de la entrada* (÷ 255).

*Filtro a mano sobre un parche 3 × 3.* Tomamos el centro de `helmet_jacket_07352.jpg` (píxel 320, 320, en gris):
#align(center)[`[[48,50,50],[46,47,49],[46,47,49]]`]
#tabla(columns: (4cm, 1fr, 1fr, 1fr),
  [Filtro], [A mano (suma de productos)], [`cv2.filter2D`], [Diferencia],
  [Promedio 3×3 (÷ 9)], [48.0], [48.0], [4·10⁻⁶],
  [Sobel horizontal Gx], [11], [11], [0],
  [Laplaciano], [4], [4], [0],
)
Cálculo a mano de Sobel Gx: columna derecha 1·50 + 2·49 + 1·49 = 197; columna izquierda 1·48 + 2·46 + 1·46 = 186; Gx = 197 − 186 = 11. Coincide con OpenCV; la diferencia del promedio es solo redondeo de coma flotante.

*¿Qué pasa sin normalizar la entrada?* Pasamos 300 imágenes de prueba directamente por la red, sin el reescalado automático de Ultralytics:
#tabla(columns: (4.4cm, 1fr, 1fr, 1fr, 1fr),
  [Entrada], [Precisión], [Recall], [F1], [Detecciones],
  [Normalizada (0–1)], [0.907], [0.890], [0.899], [1 496],
  [Sin normalizar (0–255)], [0.0007], [0.038], [0.001], [83 644],
)
La red fue entrenada con valores entre 0 y 1; con valores 255 veces mayores las activaciones se saturan y casi todas las celdas «detectan» algo: el sistema se vuelve inservible (1 524 objetos reales contra 83 644 detecciones).
Cada paso de preprocesamiento debe repetirse en producción igual que en el entrenamiento.

== D. Ajustes y mejoras
*Ajuste 1 – entrenamiento sobre el modelo preentrenado.* mAP50 en validación: época 1 = 0.805; época 10 = 0.905; época 30 = 0.938; época 60 = 0.950 (precisión 0.909, recall 0.893). Sin afinar, YOLOv8n/COCO no tiene las clases casco ni chaleco.

*Ajuste 2 – regla de asociación.* Primero bastaba que el centro del casco o chaleco cayera en cualquier parte de la caja de la persona; después exigimos regiones (casco en el tercio superior, chaleco entre el 30 % y el 75 % de la altura).
Sobre las mismas 1 393 personas detectadas:
#tabla(columns: (4cm, 1fr, 1fr, 1fr, 1fr, 1fr),
  [Regla], [Precisión], [Recall], [F1], [Acierto casco], [Acierto chaleco],
  [Antes (cualquier parte)], [0.927], [0.884], [0.905], [0.942], [0.920],
  [Después (regiones)], [0.942], [0.888], [0.914], [0.945], [0.905],
)
La mejora es pequeña (+0.9 puntos de F1) y no es uniforme: el acierto del casco sube y el del chaleco baja, porque una persona agachada o de lado cambia la proporción de su caja. Con 1 393 personas, la ganancia está cerca del margen de ruido; la mantenemos porque evita contar equipo de personas vecinas.

*Parámetro más sensible: la confianza de YOLO.* Variamos el umbral de 0.05 a 0.90 sobre las 1 050 imágenes:
#figure(image("/docs/figuras/fig_barrido_confianza.png", width: 100%), caption: [Precisión, recall y F1 según el umbral de confianza (línea punteada: 0.4 usado).])
Con 0.4 el F1 de detección es 0.895; a 0.6 la precisión sube a 0.953 pero el recall cae a 0.815, y a 0.9 el recall se hunde a 0.187. En la decisión por persona, el F1 máximo (0.918) aparece en 0.55–0.60 y a 0.4 es 0.914: la diferencia es mínima.
Un umbral alto reduce las falsas alarmas (más precisión) pero deja pasar incumplimientos reales; para seguridad conviene no perderlos, por eso conservamos 0.4 y filtramos los parpadeos con los 15 cuadros seguidos.

== E. Límites
- *Personas no detectadas:* el modelo no encuentra al 14 % de las personas (224 de 1 617). Si no hay persona, no hay alerta posible.
- *Personas lejanas* (recall 0.61) y *sobreexposición fuerte* (recall de persona 0.67 con brillo × 2).
- *Objetos parecidos al equipo* (pañuelos, gorras, ilustraciones) y *personas de espaldas o con la cabeza fuera de cuadro* (sección 8).
- *Etiquetas:* la clase persona es automática y el dataset incluye imágenes volteadas y de baja calidad; parte del «error» medido es ruido de etiquetado.
- *Probado sobre imágenes del dataset y un video de demostración*, no sobre meses de grabación real de una obra.

*¿Podría la empresa usarlo tal como está?* No todavía. Sirve como prototipo, pero faltaría: (1) reentrenar con fotos de sus propias obras, cámaras y cascos; (2) seguimiento de personas con identificador para no repetir eventos ni confundir personas que se cruzan;
(3) probar con video continuo y medir falsas alarmas por hora; (4) notificación al responsable (mensaje, sirena) y una interfaz para consultar eventos; (5) varias zonas y cámaras; (6) política de privacidad y consentimiento del personal grabado.

// ------------------------------------------------------------------ 8
= Casos de falla
En las imágenes, los recuadros blancos finos son las etiquetas del dataset; los de color son las detecciones del modelo (conf ≥ 0.4).
#let caso(img, titulo, texto) = grid(columns: (4.6cm, 1fr), gutter: 9pt, align: horizon,
  image(img, width: 4.6cm), [*#titulo.* #texto])
#caso("/docs/figuras/falla1_espaldas.jpg", "Caso 1 – persona de espaldas y cabeza fuera de cuadro",
  [Las dos personas aparecen sin cabeza (una de frente y otra de espaldas), pero el modelo detecta un «casco» (0.78 y 0.68) en el borde superior de la imagen. El chaleco sí se detecta bien (0.91 y 0.85). El sistema asume que hay casco y no alerta, aunque la falta es real. Causa: el modelo se apoya en el contexto (chaleco sobre torso) y «alucina» un casco donde se espera; el dataset tiene pocas vistas posteriores.])
#v(4pt)
#caso("/docs/figuras/falla2_panuelo.jpg", "Caso 2 – pañuelo rojo confundido con un casco",
  [Una trabajadora lleva un pañuelo rojo en la cabeza y el modelo lo detecta como *casco* con 0.74. Un trabajador sin casco quedaría marcado como protegido. Causa: color vivo y forma redondeada similares a un casco; igual ocurre con gorras. Se mitigaría con ejemplos negativos de gorras y pañuelos.])
#v(4pt)
#caso("/docs/figuras/falla3_noche.jpg", "Caso 3 – poca luz y personas pequeñas",
  [Escena nocturna con farolas: las personas son pequeñas y mal iluminadas, el equipo se detecta con confianza baja (casco 0.53, chaleco 0.71) y varias personas quedan con cajas poco precisas. Es el caso que anticipan las secciones B y E: tamaño aparente pequeño más poca luz. Mejoraría con una cámara con mejor sensor o iluminación y más ejemplos nocturnos.])
#v(4pt)
#caso("/docs/figuras/falla4_invertida.jpg", "Caso 4 – imagen volteada",
  [Parte del dataset incluye imágenes giradas 180° (aquí la escena aparece de cabeza). El modelo aún detecta cascos y chalecos, pero la regla de asociación supone la cabeza en el tercio superior de la caja, que en estas imágenes queda abajo, y se marca una falta que no existe. Causa: la regla asume personas de pie y la cámara en posición normal. En producción no pasa, pero explica errores medidos en prueba y sugiere limpiar el dataset.])
#v(4pt)
#caso("/docs/figuras/falla5_grupo.jpg", "Caso 5 – grupo de personas encimadas",
  [En el grupo las cajas de las personas se superponen, de modo que el casco o el chaleco de una puede caer dentro de la caja de la vecina; la regla del centro puede asignar equipo a quien no lo lleva. Causa: oclusión entre personas; se mejora con asociación por IoU y seguimiento por persona.])

// ------------------------------------------------------------------ 9
= Conclusiones y limitaciones
- El sistema cumple el mínimo del proyecto de punta a punta: detecta persona, casco y chaleco, asocia el equipo a cada persona, alerta solo dentro de un polígono y guarda cada evento en SQLite con captura. Además incluye el reporte por zona y hora (reto extra).
- Los números en prueba son buenos (mAP50 0.940; decisión por persona con F1 0.914), pero el principal error no está en el equipo sino en no detectar a la persona (14 %).
- El umbral de confianza es el parámetro más sensible; la normalización de la entrada es crítica; la distancia y la sobreexposición son las condiciones más dañinas.
- Limitaciones: etiquetas de persona automáticas, dataset con imágenes ruidosas o volteadas, prueba en video real limitada, sin seguimiento por identificador.
- Siguientes pasos: fotos propias de obra, seguimiento (ByteTrack), asociación por IoU, interfaz web para el cliente y despliegue como servicio.

// ------------------------------------------------------------------ 10
= Integrantes
#tabla(columns: (4.5cm, 1fr), [Integrante], [Qué hizo],
  ..integrantes.map(i => ([#falta(i.at(0))], [#falta(i.at(1))])).flatten())

#v(4pt)
#text(8.5pt, fill: gray)[Referencias: Jocher, G. et al., Ultralytics YOLOv8 (https://github.com/ultralytics/ultralytics); Lin, T.-Y. et al., Microsoft COCO (2014); #cita_dataset.]
