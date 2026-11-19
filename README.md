# Detector de EPP en obra (casco y chaleco)

Proyecto 3 del proyecto final de **Visión Artificial** (Ingeniería de Sistemas, Universidad de La Guajira).

Sistema que detecta personas, cascos y chalecos reflectivos en video, asocia el equipo a cada persona,
y **alerta cuando alguien sin casco o sin chaleco permanece dentro de una zona marcada**. Cada alerta se
guarda en una base de datos SQLite con la zona, la hora, la falta, la confianza y una captura.

**Integrantes:** [COMPLETAR]  ·  **Cliente:** [COMPLETAR]

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
3. Permite la **cámara** y la **ubicación**. Elige la zona, toca *Tomar foto* o *Grabar video*.
4. El panel está en `https://IP-DEL-PC:8000/panel` (el mapa necesita internet).

Cámara y GPS solo funcionan en HTTPS (o `localhost`). Sin `--https` la página abre en HTTP en el PC, pero el celular no dará la ubicación.
En una foto se evalúan todas las personas del encuadre (se asume que se toma dentro de la zona vigilada); en un video se analiza
medio segundo sí y medio no, y se dispara tras 3 muestras seguidas con falta.
**Privacidad:** las capturas muestran personas y ubicación; guárdalas solo con autorización de la empresa.

### Desde cualquier red (sin Wi-Fi compartido)

`python app.py --publico` abre un túnel de Cloudflare y muestra una URL `https://xxxx.trycloudflare.com` válida desde
cualquier red o datos móviles, con certificado HTTPS real (sin advertencias). Pide usuario `epp` y una clave aleatoria que se
imprime en la terminal (o la tuya con `--clave`). El PC debe quedar encendido, con internet, ejecutando la app.

```bash
sudo pacman -S cloudflared      # Arch; otros sistemas: https://github.com/cloudflare/cloudflared/releases
cd src && python app.py --publico
```

La URL cambia cada vez que se inicia. Como queda abierta a internet, la clave es obligatoria: no compartas la URL sin ella.

### Despliegue en Render (URL fija, sin depender del PC)

El repositorio incluye `Dockerfile`, `render.yaml` y `requirements-server.txt`.

1. Sube el repositorio a GitHub (con `models/best.pt`, ~6 MB).
2. En render.com: *New → Blueprint* y elige el repositorio; lee `render.yaml`.
3. Render genera la variable `EPP_CLAVE` (contraseña, usuario `epp`): cópiala desde *Environment*.
4. Abre la URL `https://epp-detector-xxxx.onrender.com` en el celular (HTTPS real: cámara y GPS funcionan).

Notas: el modelo corre en CPU (≈ 37 FPS de inferencia, suficiente para fotos y videos cortos). El plan gratuito (512 MB, sin disco, se duerme)
no sirve para este servicio: PyTorch necesita más RAM y SQLite/capturas se perderían en cada reinicio; por eso `render.yaml` usa un plan de pago
con disco persistente en `/data` (variable `DATA_DIR`). Verifica los precios vigentes antes de crear el servicio.

### Despliegue gratuito en Hugging Face Spaces

1. Crea una cuenta en huggingface.co y un token de escritura (Settings → Access Tokens → *Write*).
2. *New Space* → SDK **Docker** → plan gratuito *CPU basic* → visibilidad a tu gusto. Deja el Space vacío.
3. En el Space: *Settings → Variables and secrets → New secret*: `EPP_CLAVE` = la contraseña (usuario `epp`).
4. Desde este repositorio:
   ```bash
   scripts/publicar_hf.sh TU_USUARIO NOMBRE_DEL_SPACE   # usuario HF y token como contraseña
   ```
5. Espera el *build* (varios minutos) y abre `https://tu_usuario-nombre_del_space.hf.space` (no la página de huggingface.co:
   dentro de ese marco el navegador bloquea cámara y GPS).

El disco del plan gratuito es temporal: los eventos se pierden si el Space se reinicia o se duerme.

## Datos y entrenamiento

- 10 500 imágenes con 48 597 cajas (casco 18 528, chaleco 14 516, persona 15 553). División 70/20/10:
  7 350 entrenamiento, 2 100 validación, 1 050 prueba.
- Origen: **[COMPLETAR: dataset de Kaggle citado + fotos propias]**. Dataset: **[COMPLETAR enlace]**.
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
```

## Limitaciones

Falla con personas de espaldas o con la cabeza fuera de cuadro, objetos parecidos a cascos (pañuelos, gorras),
poca luz y personas lejanas. Las etiquetas de *persona* son automáticas (COCO) y se revisaron por muestra.
