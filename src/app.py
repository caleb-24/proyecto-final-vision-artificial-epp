"""App web: captura foto/video con ubicación real desde el celular y panel de eventos.

    python app.py                 # http://localhost:8000
    python app.py --https         # https://IP-DEL-PC:8000  (misma red Wi-Fi; certificado autofirmado)
    python app.py --publico       # URL pública HTTPS, funciona desde cualquier red

/            página de captura (móvil): foto o video + GPS -> análisis -> evento guardado
/panel       mapa y tabla de eventos + reporte por zona y hora
/api/registro, /api/login, /api/yo   autenticación de usuarios con Supabase Auth
"""
import argparse
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from functools import wraps
from pathlib import Path

import cv2
import numpy as np
import torch
from flask import Flask, Response, g, jsonify, request, send_from_directory
from ultralytics import YOLO

import auth
import db
from detector import equipo_con_conf, faltas_persona, separar

RAIZ = Path(__file__).resolve().parents[1]
DATOS = Path(os.environ.get("DATA_DIR", RAIZ))
CAPTURAS = DATOS / "capturas"
BD = DATOS / "eventos.db"
WEB = Path(__file__).resolve().parent / "web"
CAPTURAS.mkdir(parents=True, exist_ok=True)
CONF = 0.4
MUESTRAS_ALERTA = 3          # en video: muestras seguidas con falta para disparar (≈1.5 s)
MUESTRAS_POR_SEG = 2
MAX_SEG_VIDEO = 60
VERDE, ROJO, GRIS = (60, 200, 60), (40, 40, 230), (170, 170, 170)

modelo = YOLO(str(RAIZ / "models" / "best.pt"))
DEV = 0 if torch.cuda.is_available() else "cpu"
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024


def requiere_usuario(f):
    """Exige un token de Supabase Auth válido en el header Authorization."""
    @wraps(f)
    def envuelto(*args, **kwargs):
        cabecera = request.headers.get("Authorization", "")
        token = cabecera[7:].strip() if cabecera.startswith("Bearer ") else ""
        usuario = auth.usuario_actual(token)
        if not usuario:
            return jsonify(error="Inicia sesión para continuar"), 401
        g.usuario = usuario
        g.token = token
        return f(*args, **kwargs)
    return envuelto


@app.post("/api/registro")
def api_registro():
    datos = request.get_json(silent=True) or {}
    email = str(datos.get("email") or "").strip().lower()
    clave = str(datos.get("password") or "")
    if "@" not in email or len(clave) < 6:
        return jsonify(error="Escribe un correo válido y una contraseña de al menos 6 caracteres"), 400
    try:
        return jsonify(auth.crear_cuenta(email, clave))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception:
        return jsonify(error="No se pudo conectar con Supabase Auth"), 503


@app.post("/api/login")
def api_login():
    datos = request.get_json(silent=True) or {}
    email = str(datos.get("email") or "").strip().lower()
    clave = str(datos.get("password") or "")
    if not email or not clave:
        return jsonify(error="Correo y contraseña son obligatorios"), 400
    try:
        return jsonify(auth.iniciar_sesion(email, clave))
    except ValueError as e:
        return jsonify(error=str(e)), 401
    except Exception:
        return jsonify(error="No se pudo conectar con Supabase Auth"), 503


@app.get("/api/yo")
@requiere_usuario
def api_yo():
    return jsonify(usuario=g.usuario.get("email"), id=g.usuario.get("id"))


def analizar(frame):
    """Detecta y evalúa a cada persona. Devuelve (incumplimientos, personas, imagen anotada, (cascos, chalecos))."""
    res = modelo(frame, conf=CONF, device=DEV, verbose=False)[0]
    cascos, chalecos, personas = separar(res)
    esc = max(frame.shape[:2]) / 960
    grosor = max(2, int(2 * esc))
    incumplen = []
    def rotular(x, y, texto, color, txt=(255, 255, 255), tam=0.6):
        (w, h), base = cv2.getTextSize(texto, 0, tam * esc, max(1, grosor - 1))
        x = int(max(0, min(x, frame.shape[1] - w - 8)))
        y = int(max(h + 8, y))
        cv2.rectangle(frame, (x, y - h - 8), (x + w + 8, y + base - 2), color, -1)
        cv2.putText(frame, texto, (x + 4, y - 4), 0, tam * esc, txt, max(1, grosor - 1), cv2.LINE_AA)

    cascos_c, chalecos_c = equipo_con_conf(res)
    for b, cf in cascos_c:
        cv2.rectangle(frame, tuple(map(int, b[:2])), tuple(map(int, b[2:])), (0, 220, 255), grosor)
        rotular(b[0], b[3] - 2, f"Casco {cf:.0%}", (0, 220, 255), (0, 0, 0), 0.5)
    for b, cf in chalecos_c:
        cv2.rectangle(frame, tuple(map(int, b[:2])), tuple(map(int, b[2:])), (0, 140, 255), grosor)
        rotular(b[0], b[3] - 2, f"Chaleco {cf:.0%}", (0, 140, 255), (0, 0, 0), 0.5)
    for p, pc in personas:
        fc, fch = faltas_persona(p, cascos, chalecos)
        color = ROJO if (fc or fch) else VERDE
        txt = "SIN " + " y ".join(n for n, f in (("CASCO", fc), ("CHALECO", fch)) if f) if (fc or fch) else "EPP completo"
        x1, y1, x2, y2 = map(int, p)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, grosor + 1)
        rotular(x1, y1 - 2, f"Persona: {txt} {pc:.0%}", color)
        if fc or fch:
            incumplen.append((fc, fch, float(pc)))
    return incumplen, len(personas), frame, (len(cascos), len(chalecos))


def _guardar_jpeg(frame, ruta):
    """JPEG comprimido: la preview en el celular baja mucho más rápido por el túnel."""
    cv2.imwrite(str(ruta), frame, [cv2.IMWRITE_JPEG_QUALITY, 70])


def guardar_evento(frame, incumplen, zona, lat, lon, prec, origen, usuario=None):
    fc = any(i[0] for i in incumplen)
    fch = any(i[1] for i in incumplen)
    cf = max(i[2] for i in incumplen)
    ruta = CAPTURAS / f"app_{int(time.time() * 1000)}.jpg"
    _guardar_jpeg(frame, ruta)
    con = db.conectar(BD)
    try:
        return db.registrar_evento(con, zona, fc, fch, cf, ruta, lat, lon, prec, origen, usuario), ruta.name, fc, fch
    finally:
        con.close()


def _num(nombre):
    try:
        return float(request.form[nombre])
    except (KeyError, ValueError):
        return None


@app.post("/api/analizar")
@requiere_usuario
def api_analizar():
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify(error="Falta el archivo"), 400
    zona = (request.form.get("zona") or "Zona 1").strip()[:60]
    lat, lon, prec = _num("lat"), _num("lon"), _num("precision")
    if lat is not None and lon is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
        lat = lon = prec = None
    usuario = g.usuario.get("email")
    datos = archivo.read()
    es_video = (archivo.mimetype or "").startswith("video") or archivo.filename.lower().endswith((".mp4", ".mov", ".webm", ".avi", ".mkv"))

    if not es_video:
        frame = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify(error="No pude leer la imagen"), 400
        incumplen, n, anotada, eq = analizar(frame)
        out = dict(tipo="foto", personas=n, cascos=eq[0], chalecos=eq[1], incumplimientos=len(incumplen), eventos=[])
        if incumplen:
            eid, nombre, fc, fch = guardar_evento(anotada, incumplen, zona, lat, lon, prec, "app", usuario)
            out["eventos"].append(dict(id=eid, imagen=f"/capturas/{nombre}", falta_casco=fc, falta_chaleco=fch))
            elegida = nombre
        else:
            tmp = CAPTURAS / f"app_ok_{int(time.time() * 1000)}.jpg"   # se muestra, pero no es un evento
            _guardar_jpeg(anotada, tmp)
            elegida = tmp.name
        out["imagen"] = f"/capturas/{elegida}"
        out["con_ubicacion"] = lat is not None
        return jsonify(out)

    # --- video: se muestrea cada 0.5 s; dispara tras MUESTRAS_ALERTA muestras seguidas con falta
    with tempfile.NamedTemporaryFile(suffix=Path(archivo.filename or "v.mp4").suffix or ".mp4", delete=False) as f:
        f.write(datos)
        ruta_tmp = f.name
    cap = cv2.VideoCapture(ruta_tmp)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    paso = max(1, int(fps / MUESTRAS_POR_SEG))
    i = seguidas = analizadas = pers_max = cascos_max = chalecos_max = 0
    armado = True
    eventos = []
    mejor, mejor_n = None, -1        # cuadro con más personas (se muestra si no hay evento)
    while i < fps * MAX_SEG_VIDEO:
        ok, frame = cap.read()
        if not ok:
            break
        if i % paso == 0:
            incumplen, n, anotada, eq = analizar(frame)
            analizadas += 1
            cascos_max, chalecos_max = max(cascos_max, eq[0]), max(chalecos_max, eq[1])
            pers_max = max(pers_max, n)
            if n > mejor_n:
                mejor, mejor_n = anotada.copy(), n
            if incumplen:
                seguidas += 1
                if seguidas >= MUESTRAS_ALERTA and armado:
                    armado = False
                    eid, nombre, fc, fch = guardar_evento(anotada, incumplen, zona, lat, lon, prec, "app", usuario)
                    eventos.append(dict(id=eid, imagen=f"/capturas/{nombre}", falta_casco=fc, falta_chaleco=fch))
            else:
                seguidas = 0
                armado = True
        i += 1
    cap.release()
    Path(ruta_tmp).unlink(missing_ok=True)
    if analizadas == 0:
        return jsonify(error="No pude leer el video"), 400
    out = dict(tipo="video", muestras=analizadas, personas=pers_max, cascos=cascos_max, chalecos=chalecos_max, incumplimientos=len(eventos), eventos=eventos,
               con_ubicacion=lat is not None)
    if eventos:
        out["imagen"] = eventos[0]["imagen"]
    elif mejor is not None:
        tmp = CAPTURAS / f"app_ok_{int(time.time() * 1000)}.jpg"
        _guardar_jpeg(mejor, tmp)
        out["imagen"] = f"/capturas/{tmp.name}"
    return jsonify(out)


@app.get("/api/eventos")
@requiere_usuario
def api_eventos():
    con = db.conectar(BD)
    try:
        ev = db.eventos_dict(con)
        for e in ev:
            ruta = e.get("ruta_captura") or ""
            e["imagen"] = ruta if ruta.startswith("http") else "/capturas/" + Path(ruta).name
        rep = [dict(zona=z, hora=h, eventos=n, sin_casco=c, sin_chaleco=ch) for z, h, n, c, ch in db.reporte_zona_hora(con)]
        respuesta = jsonify(eventos=ev, reporte=rep)
        respuesta.headers["Cache-Control"] = "no-store"
        return respuesta
    finally:
        con.close()


@app.get("/capturas/<path:nombre>")
def capturas(nombre):
    return send_from_directory(CAPTURAS, nombre)


@app.get("/auth.js")
def auth_js():
    return send_from_directory(WEB, "auth.js")


@app.get("/healthz")
def healthz():
    return "ok"


@app.get("/")
def index():
    return send_from_directory(WEB, "captura.html")


@app.get("/panel")
def panel():
    return send_from_directory(WEB, "panel.html")


def iniciar_tunel(puerto):
    """Abre un túnel HTTPS público y devuelve (url, proceso)."""
    exe = shutil.which("cloudflared") or str(Path.home() / ".local" / "bin" / "cloudflared")
    if Path(exe).exists():
        cmd = [exe, "tunnel", "--url", f"http://localhost:{puerto}", "--no-autoupdate"]
        patron = r"https://[a-z0-9-]+\.trycloudflare\.com"
    elif shutil.which("ssh"):
        cmd = ["ssh", "-T", "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=30",
               "-o", "ExitOnForwardFailure=yes", "-R", f"80:localhost:{puerto}", "nokey@localhost.run"]
        patron = r"https://(?!admin\.)(?:[a-z0-9-]+\.)+lhr\.life"
    else:
        raise SystemExit("No encuentro cloudflared ni ssh. Instala cloudflared (ver README).")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url = []

    def leer():
        for linea in proc.stdout:
            m = re.search(patron, linea)
            if m and not url:
                url.append(m.group(0))
    threading.Thread(target=leer, daemon=True).start()
    for _ in range(60):
        if url:
            return url[0], proc
        time.sleep(0.5)
    proc.terminate()
    raise SystemExit("El túnel no respondió. Revisa tu conexión a internet.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=8000)
    ap.add_argument("--https", action="store_true", help="certificado autofirmado (misma red Wi-Fi)")
    ap.add_argument("--publico", action="store_true", help="URL pública HTTPS (cualquier red)")
    a = ap.parse_args()
    if a.publico:
        url, _tunel = iniciar_tunel(a.puerto)
        print(f"\n  App pública:  {url}\n  Panel:        {url}/panel\n  Los usuarios se crean con Correo y Contraseña en la pantalla de acceso.\n")
    app.run(host="127.0.0.1" if a.publico else "0.0.0.0", port=a.puerto,
            ssl_context="adhoc" if a.https and not a.publico else None, threaded=True)
