# Detector de EPP en obra (casco y chaleco)

Proyecto 3 del proyecto final de **Visión Artificial** (Ingeniería de Sistemas, Universidad de La Guajira).

Sistema que detecta personas, cascos y chalecos reflectivos en video, asocia el equipo a cada persona,
y **alerta cuando alguien sin casco o sin chaleco permanece dentro de una zona marcada**. Cada alerta se
guarda en una base de datos SQLite con la zona, la hora, la falta, la confianza y una captura.

**Integrantes:** Caleb Reyes (servidor en Docker e integración con Expo) · Denison Cuello (interfaz en Expo Go) · Camilo Gómez (repositorio)  ·  **Cliente:** R&H Suministros Asesorías y Consultorías SAS

## Ficha rápida

| Dato | Valor |
|---|---|
| Asignatura | Visión Artificial · Ingeniería de Sistemas · Universidad de La Guajira |
| Docente | Eduardo Sierra Fragozo |
| Entrega | Proyecto 3 · 24 de noviembre de 2026 |
| Modelo | YOLOv8n, 60 épocas, 3 clases (casco, chaleco, persona) |
| Resultado principal | mAP50 0.940; decisión «incumple» F1 0.914 |
| Informe | [`docs/informe.pdf`](docs/informe.pdf) (9 páginas) |
| Repositorio | https://github.com/caleb-24/proyecto-final-vision-artificial-epp |
| Dataset publicado | https://huggingface.co/buckets/CJ305/proyecto-final-vision-artificial-epp-storage |
| Video demo | https://drive.google.com/drive/u/1/folders/1jgoJFF7JHdzBCA3dNVkgTr-876-0_3-d (`prueba web.mp4` y `prueba movil.mp4`, ~2:34 c/u) |
| Tecnologías | Python, Flask, OpenCV, Ultralytics YOLOv8, SQLite/Supabase, Docker, React Native (Expo SDK 58) |

## Cómo funciona

```
video → YOLOv8n (persona, casco, chaleco) → asociación persona-equipo → ¿dentro del polígono?
      → ¿falta se mantiene 15 cuadros? → alerta + captura + fila en SQLite (tabla eventos)
```

| Archivo | Qué hace |
|---|---|
| `src/detector.py` | clases del modelo y reglas que asocian casco/chaleco a cada persona |
| `src/db.py` | conexión SQLite, inserción de eventos y consulta por zona y hora |
| `src/sistema.py` | programa principal: video → detección → zona → alerta → base de datos |
| `src/app.py` + `src/web/` | **app web**: captura foto/video desde el celular con ubicación GPS y panel con mapa |
| `mobile/` | app móvil Expo (React Native) para capturar y consultar eventos |
| `src/reporte.py` | reporte de incumplimientos por zona y por hora (reto extra) |
| `db/schema.sql` | creación de la tabla `eventos` |
| `models/best.pt` | pesos entrenados (YOLOv8n, 60 épocas) |
| `scripts/` | preparación del dataset (`prellenar.py`, `limpiar.py`, `mover.py`, `verificar.py`), demo y experimentos (`analisis.py`) |
| `resultados/` | curvas, matriz de confusión y `analisis/analisis.json` |
| `docs/` | informe y figuras |

## Instalación

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # ultralytics, opencv-python, matplotlib, numpy
```

## Ejecutar

```bash
cd src
python sistema.py RUTA/AL/VIDEO.mp4          # primera vez: 4 clics sobre la zona y Enter
python sistema.py 0                          # webcam
python sistema.py video.mp4 --redefinir-zona # volver a marcar la zona
python sistema.py video.mp4 --zona "0,0;959,0;959,959;0,959"   # sin ventana
python reporte.py                            # eventos y conteo por zona y hora
```

Salidas (en la raíz del repositorio): `demo_anotada.mp4`, `capturas/`, `eventos.db`, `zona.json`.
Opciones: `--conf` (umbral de YOLO, 0.4 por defecto) y `--cuadros` (cuadros seguidos para alertar, 15).

Para grabar un video de prueba con la webcam y para una demo sobre imágenes del dataset:
`python scripts/crear_demo_dataset.py data/safety-Helmet-Reflective-Jacket`.

## App web: foto o video con ubicación real

El celular abre una página, toma la foto o el video, lee el GPS, y el servidor corre el mismo modelo y guarda el evento
(con latitud, longitud y precisión) en la tabla `eventos`. El panel muestra los eventos en un mapa y el reporte por zona y hora.

```bash
cd src
python app.py --https         # el PC y el celular deben estar en la misma red Wi-Fi
```

1. En el PC averigua su IP local (`ip -4 addr` en Linux).
2. En el celular abre `https://IP-DEL-PC:8000`. El certificado es autofirmado: acepta la advertencia del navegador (Avanzado → continuar).
3. En la pantalla de acceso toca **Crear cuenta** (correo y contraseña) o **Iniciar sesión** si ya tienes cuenta.
4. Permite la **cámara** y la **ubicación**. Elige la zona, toca *Tomar foto* o *Grabar video*.
5. El panel está en `https://IP-DEL-PC:8000/panel` (el mapa necesita internet).

Cámara y GPS solo funcionan en HTTPS (o `localhost`). Sin `--https` la página abre en HTTP en el PC, pero el celular no dará la ubicación.
En una foto se evalúan todas las personas del encuadre (se asume que se toma dentro de la zona vigilada); en un video se analiza
medio segundo sí y medio no, y se dispara tras 3 muestras seguidas con falta.
**Privacidad:** las capturas muestran personas y ubicación; guárdalas solo con autorización de la empresa.

### Acceso de usuarios

La clave compartida (`epp`) ya no existe: cada persona entra con su propio correo y contraseña (Supabase Auth).

- **Crear cuenta:** botón *Crear cuenta* en la web o en Expo, o `POST /api/registro` con `{"email":"...","password":"..."}`.
- **Entrar:** botón *Iniciar sesión* o `POST /api/login`. La respuesta trae un `access_token`.
- Ese token se guarda en el navegador (`localStorage`) o en la app (`AsyncStorage`) y se envía como `Authorization: Bearer ...`.
  `/api/analizar`, `/api/eventos` y `/api/yo` lo exigen; sin él responden 401.
- Cada evento guarda en la columna `usuario` el correo de quien lo reportó.

Para la demo conviene desactivar la confirmación por correo en Supabase → *Authentication → Providers → Email → Confirm email*.
Así `/api/registro` devuelve sesión de inmediato y no se consume el límite de correos del plan gratuito. Si está activa, el usuario debe
confirmar el correo antes de poder entrar.

### API REST

| Método | Ruta | Autenticación | Qué hace |
|---|---|---|---|
| GET | `/` | no | Página de captura (foto/video + GPS) |
| GET | `/panel` | no | Panel con mapa, KPIs y reporte por zona/hora |
| GET | `/healthz` | no | Chequeo de salud: responde `ok` |
| POST | `/api/registro` | no | Crea usuario (correo y contraseña) con Supabase Auth |
| POST | `/api/login` | no | Devuelve `access_token` y correo |
| GET | `/api/yo` | Bearer | Usuario actual |
| POST | `/api/analizar` | Bearer | Sube foto/video (`multipart/form-data`, campo `archivo`), analiza y guarda el evento |
| GET | `/api/eventos` | Bearer | Lista eventos (con `imagen`, latitud, longitud) y reporte agregado |
| GET | `/capturas/<archivo>` | no | Imagen anotada guardada en `capturas/` |

`/api/analizar` acepta además `zona`, `lat`, `lon` y `precision` como campos de formulario. Para foto devuelve
`tipo`, `personas`, `cascos`, `chalecos`, `incumplimientos`, `eventos` e `imagen`; para video muestrea cada 0.5 s
durante hasta 60 s y dispara la alerta tras 3 muestras seguidas con falta.

### Desde cualquier red (túnel público)

`python app.py --publico` abre un túnel HTTPS y muestra una URL pública, válida desde cualquier red o datos móviles,
con certificado real (cámara y GPS del celular funcionan). Usa `cloudflared` si está instalado y, si no, un túnel SSH con
[localhost.run](https://localhost.run) (no requiere instalar nada ni crear cuenta).

```bash
cd src
python app.py --publico      # imprime la URL (https://xxxx.lhr.life)
```

La URL cambia cada vez que se inicia. El PC debe estar encendido, con internet y con la app corriendo. El sitio es público, pero los datos
solo se ven con un token de usuario válido.

## App móvil con Expo (`mobile/`)

App de React Native (Expo SDK 58). Al abrirla muestra la pantalla de **Iniciar sesión / Crear cuenta**; después tiene tres pestañas:
**Capturar** (foto, video o galería + GPS), **Eventos** (lista con foto y ubicación) y **Ajustes** (servidor y *Cerrar sesión*).
Envía todo a la misma API con el token (`/api/analizar`, `/api/eventos`).

```bash
cd mobile
npm install
npx expo start --tunnel        # QR para abrirla en Expo Go desde cualquier red
```

1. Instala **Expo Go** en el celular (Play Store / App Store) y escanea el QR. Con `--tunnel` funciona aunque el celular no esté en la misma Wi-Fi.
2. Escribe la URL pública del servidor (la de `python app.py --publico`), tu correo y tu contraseña; toca *Crear cuenta* o *Iniciar sesión*.
3. En *Capturar*, permite cámara y ubicación y toma una foto o un video. En *Ajustes* puedes cerrar sesión.

Nota: el reporte en video grabado con la cámara depende de Expo Go en cada teléfono; si no abre la cámara de video, usa *Galería*.

### Despliegue como API en contenedor Docker

La app es una API Flask (`/api/analizar`, `/api/eventos`) con su panel (`/panel`) y se empaqueta en el `Dockerfile` de la raíz
(PyTorch solo CPU, `gunicorn`, 1 worker). El modelo viaja dentro de la imagen y los datos se guardan en `/data`.

```bash
docker build -t epp-detector .
docker run -p 8000:7860 --env-file .env -v epp-datos:/data epp-detector
# abrir http://localhost:8000 e iniciar sesión con tu correo/contraseña
```

Para abrirla desde el celular fuera de tu red, combina cualquiera de las dos formas con el túnel de la sección anterior
(`python src/app.py --publico`). El mismo `Dockerfile` sirve para desplegar en un servicio de contenedores en la nube
(Cloud Run, Render, Azure…) si más adelante se activa la facturación; no está desplegado en ninguno.

## Base de datos en la nube (Supabase)

Los eventos y las capturas se pueden guardar en Supabase en vez del SQLite local. La autenticación de personas también la gestiona Supabase Auth; el navegador y la app móvil solo guardan el token, nunca la contraseña.

1. Crea el proyecto en https://database.new.
2. En el *SQL Editor* pega y ejecuta `db/supabase.sql`: crea la tabla `eventos`, el bucket público `capturas` y sus políticas.
3. Crea un archivo `.env` en la raíz del repositorio (ya está en `.gitignore`):

```bash
SUPABASE_URL=https://TU-PROYECTO.supabase.co
SUPABASE_KEY=TU_CLAVE_PUBLISHABLE
```

   También funciona con `SUPABASE_SERVICE_ROLE_KEY` en lugar de `SUPABASE_KEY` (más seguro: bypassa RLS y no depende de las políticas públicas). La clave publishable es la que entrega el MCP y ya está autorizada por las políticas de `db/supabase.sql`.

4. Reinicia `app.py`, `sistema.py` o `reporte.py`. Con las dos variables definidas, todos escriben y leen en Supabase; sin ellas siguen usando `eventos.db`. Las capturas se suben al Storage y el panel muestra su URL pública.

Si usas Docker, pasa el mismo archivo al contenedor:

```bash
docker run -p 8000:7860 --env-file .env epp-detector
```

## Esquema de datos

Tabla `eventos` (`db/schema.sql`, espejo en `db/supabase.sql`):

| Columna | Tipo | Contenido |
|---|---|---|
| `id` | INTEGER PK | Identificador autoincremental |
| `momento` | TEXT | Fecha y hora ISO 8601 del evento |
| `zona` | TEXT | Nombre de la zona vigilada |
| `falta_casco`, `falta_chaleco` | INTEGER | 1 si faltaba cada equipo |
| `confianza` | REAL | Confianza de la detección de la persona |
| `ruta_captura` | TEXT | Imagen con las cajas dibujadas |
| `latitud`, `longitud`, `precision_m` | REAL/INTEGER | GPS del celular (opcional) |
| `origen` | TEXT | `video`, `webcam` o `app` |
| `usuario` | TEXT | Correo de quien reportó el evento |

El reporte `python src/reporte.py` agrupa incumplimientos por zona y por hora (reto extra del proyecto).

## Datos y entrenamiento

- 10 500 imágenes con 48 597 cajas (casco 18 528, chaleco 14 516, persona 15 553). División 70/20/10:
  7 350 entrenamiento, 2 100 validación, 1 050 prueba.
- Origen: dataset público de Kaggle (Nirav Naik, «Safety Helmet and Reflective Jacket», https://www.kaggle.com/datasets/niravnaik/safety-helmet-and-reflective-jacket/data, consultado el 24 de nov de 2026). No se dispuso de fotos propias etiquetadas. Dataset publicado (10 500 imágenes, 586 MB): https://huggingface.co/buckets/CJ305/proyecto-final-vision-artificial-epp-storage
- La clase *persona* se pre-llenó con YOLOv8n preentrenado en COCO (`scripts/prellenar.py`, conf 0.4).
- Entrenamiento: YOLOv8n preentrenado, 60 épocas, imagen 640, lote 8, GPU (≈75 min).

## Métricas (1 050 imágenes de prueba)

| Clase | mAP50 | Precisión | Recall |
|---|---|---|---|
| Casco | 0.955 | 0.934 | 0.904 |
| Chaleco | 0.951 | 0.891 | 0.897 |
| Persona | 0.914 | 0.894 | 0.826 |
| **Global** | **0.940** | **0.906** | **0.876** |

Decisión del sistema por persona («incumple»): precisión 0.94, recall 0.89, F1 0.91 con conf 0.4.
Velocidad: ~137 FPS en GPU y ~37 FPS en CPU (solo inferencia). Detalles en `docs/informe.pdf`.

## Reproducir los experimentos

```bash
python scripts/analisis.py data/safety-Helmet-Reflective-Jacket
# resultados en resultados/analisis/analisis.json
```

| Experimento | Resultado |
|---|---|
| Filtro 3×3 a mano vs OpenCV | Diferencia 4·10⁻⁶ (suma de productos 48.0) |
| Entrada sin normalizar (0–255) | F1 cae de 0.899 a 0.001 (83 644 detecciones falsas) |
| Entrenamiento desde cero vs preentrenado | mAP50 0.805 (época 1) → 0.905 (10) → 0.950 (60) |
| Regla de asociación antes/después | F1 0.905 → 0.914; acierto de casco 0.942 → 0.945 |
| Barrido de confianza | Con 0.4, F1 0.895; con 0.6 sube la precisión a 0.953 pero el recall baja a 0.815 |
| Distancia (tamaño de persona) | Recall 0.61 lejos, 0.80 medio, 0.90 cerca |
| Iluminación | F1 global 0.900 original, 0.835 con brillo ×2 |

## Limitaciones

Falla con personas de espaldas o con la cabeza fuera de cuadro, objetos parecidos a cascos (pañuelos, gorras),
poca luz y personas lejanas. Las etiquetas de *persona* son automáticas (COCO) y se revisaron por muestra.
El modelo no encuentra al ~14 % de las personas del conjunto de prueba (224 de 1 617) y en grupos pegados detecta 1 de 5.
El dataset original tiene algunas imágenes volteadas 180°.

## Solución de problemas

| Síntoma | Causa y solución |
|---|---|
| «no tunnel» en el celular | La URL pública guardada quedó vieja. Vuelve a correr `python src/app.py --publico`, copia la URL nueva y pégala en *Ajustes* de la app. |
| Cámara o GPS no funcionan | Requieren HTTPS (o `localhost`): usa `--https` en la misma Wi-Fi o `--publico` desde cualquier red. |
| La imagen tarda en aparecer en Expo | El túnel público es lento; espera unos segundos o toca *Reintentar imagen*. La foto se reduce a 960 px antes de subir. |
| El panel no muestra una foto | El panel solo lista **eventos** (cuando hay falta de casco o chaleco). Una foto con «EPP completo» no genera evento. |
| `Fetch request has been canceled` | El servidor tardó más de 90 s. Revisa la URL en *Ajustes* y la conexión; vuelve a intentar. |
| `docker: Cannot connect to the Docker daemon` | El daemon está apagado: `sudo systemctl start docker` (necesita contraseña del usuario). |
| `Permission denied` al hacer `git push` | La cuenta activa de `gh` debe ser `caleb-24`: `gh auth switch --user caleb-24`. |
| No entra un usuario recién creado | Confirma el correo o desactiva *Confirm email* en Supabase Auth. |

## Enlaces

- **Repositorio:** https://github.com/caleb-24/proyecto-final-vision-artificial-epp
- **Informe PDF:** [`docs/informe.pdf`](docs/informe.pdf)
- **Dataset en Kaggle:** https://www.kaggle.com/datasets/niravnaik/safety-helmet-and-reflective-jacket/data
- **Dataset publicado:** https://huggingface.co/buckets/CJ305/proyecto-final-vision-artificial-epp-storage
- **Videos demo:** https://drive.google.com/drive/u/1/folders/1jgoJFF7JHdzBCA3dNVkgTr-876-0_3-d
- **YOLOv8 (Ultralytics):** https://github.com/ultralytics/ultralytics
