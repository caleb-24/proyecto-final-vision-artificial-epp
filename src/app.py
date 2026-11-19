"""App web: captura foto/video con ubicación real desde el celular y panel de eventos.

    python app.py                 # http://localhost:8000
    python app.py --https         # https://IP-DEL-PC:8000  (misma red Wi-Fi; certificado autofirmado)
    python app.py --publico       # URL pública https://xxxx.trycloudflare.com, funciona desde cualquier red

/            página de captura (móvil): foto o video + GPS -> análisis -> evento guardado
/panel       mapa y tabla de eventos + reporte por zona y hora
"""
import argparse
import hmac
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from flask import Flask, Response, jsonify, request, send_from_directory
from ultralytics import YOLO

import db
from detector import equipo_con_conf, faltas_persona, separar

RAIZ = Path(__file__).resolve().parents[1]
DATOS = Path(os.environ.get("DATA_DIR", RAIZ))   # en Render apunta al disco persistente (/data)
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
CLAVE = os.environ.get("EPP_CLAVE")      # si existe, todo el sitio pide usuario «epp» y esta clave


@app.before_request
def pedir_clave():
    if not CLAVE or request.path == "/healthz":
        return None
    a = request.authorization
    if a and a.username == "epp" and hmac.compare_digest(a.password or "", CLAVE):
        return None
    return Response("Acceso restringido", 401, {"WWW-Authenticate": 'Basic realm="Reporte EPP"'})


def analizar(frame):
    """Detecta y evalúa a cada persona. Devuelve (lista de incumplimientos, personas totales, imagen anotada)."""
    res = modelo(frame, conf=CONF, device=DEV, verbose=False)[0]
    cascos, chalecos, personas = separar(res)
    esc = max(frame.shape[:2]) / 960
    g = max(2, int(2 * esc))
    incumplen = []
    def rotular(x, y, texto, color, txt=(255, 255, 255), tam=0.6):
        (w, h), base = cv2.getTextSize(texto, 0, tam * esc, max(1, g - 1))
        x = int(max(0, min(x, frame.shape[1] - w - 8)))
        y = int(max(h + 8, y))
        cv2.rectangle(frame, (x, y - h - 8), (x + w + 8, y + base - 2), color, -1)
        cv2.putText(frame, texto, (x + 4, y - 4), 0, tam * esc, txt, max(1, g - 1), cv2.LINE_AA)

    cascos_c, chalecos_c = equipo_con_conf(res)
    for b, cf in cascos_c:
        cv2.rectangle(frame, tuple(map(int, b[:2])), tuple(map(int, b[2:])), (0, 220, 255), g)
        rotular(b[0], b[3] - 2, f"Casco {cf:.0%}", (0, 220, 255), (0, 0, 0), 0.5)
    for b, cf in chalecos_c:
        cv2.rectangle(frame, tuple(map(int, b[:2])), tuple(map(int, b[2:])), (0, 140, 255), g)
        rotular(b[0], b[3] - 2, f"Chaleco {cf:.0%}", (0, 140, 255), (0, 0, 0), 0.5)
    for p, pc in personas:
        fc, fch = faltas_persona(p, cascos, chalecos)
        color = ROJO if (fc or fch) else VERDE
        txt = "SIN " + " y ".join(n for n, f in (("CASCO", fc), ("CHALECO", fch)) if f) if (fc or fch) else "EPP completo"
        x1, y1, x2, y2 = map(int, p)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, g + 1)
        rotular(x1, y1 - 2, f"Persona: {txt} {pc:.0%}", color)
        if fc or fch:
            incumplen.append((fc, fch, float(pc)))
    return incumplen, len(personas), frame


def guardar_evento(frame, incumplen, zona, lat, lon, prec, origen):
    fc = any(i[0] for i in incumplen)
    fch = any(i[1] for i in incumplen)
    cf = max(i[2] for i in incumplen)
    ruta = CAPTURAS / f"app_{int(time.time() * 1000)}.jpg"
    cv2.imwrite(str(ruta), frame)
    con = db.conectar(BD)
    try:
        return db.registrar_evento(con, zona, fc, fch, cf, ruta, lat, lon, prec, origen), ruta.name, fc, fch
    finally:
        con.close()


def _num(nombre):
    try:
        return float(request.form[nombre])
    except (KeyError, ValueError):
        return None


@app.post("/api/analizar")
def api_analizar():
    archivo = request.files.get("archivo")
    if archivo is None:
        return jsonify(error="Falta el archivo"), 400
    zona = (request.form.get("zona") or "Zona 1").strip()[:60]
    lat, lon, prec = _num("lat"), _num("lon"), _num("precision")
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
        lat = lon = prec = None
    datos = archivo.read()
    es_video = (archivo.mimetype or "").startswith("video") or archivo.filename.lower().endswith((".mp4", ".mov", ".webm", ".avi", ".mkv"))

    if not es_video:
        frame = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify(error="No pude leer la imagen"), 400
        incumplen, n, anotada = analizar(frame)
        out = dict(tipo="foto", personas=n, incumplimientos=len(incumplen), eventos=[])
        if incumplen:
            eid, nombre, fc, fch = guardar_evento(anotada, incumplen, zona, lat, lon, prec, "app")
            out["eventos"].append(dict(id=eid, imagen=f"/capturas/{nombre}", falta_casco=fc, falta_chaleco=fch))
            out["imagen"] = f"/capturas/{nombre}"
        else:
            tmp = CAPTURAS / f"app_ok_{int(time.time() * 1000)}.jpg"   # se muestra, pero no es un evento
            cv2.imwrite(str(tmp), anotada)
            out["imagen"] = f"/capturas/{tmp.name}"
        out["con_ubicacion"] = lat is not None
        return jsonify(out)

    # --- video: se muestrea cada 0.5 s; dispara tras MUESTRAS_ALERTA muestras seguidas con falta
    with tempfile.NamedTemporaryFile(suffix=Path(archivo.filename or "v.mp4").suffix or ".mp4", delete=False) as f:
        f.write(datos)
        ruta_tmp = f.name
    cap = cv2.VideoCapture(ruta_tmp)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    paso = max(1, int(fps / MUESTRAS_POR_SEG))
    i = seguidas = analizadas = pers_max = 0
    armado = True
    eventos = []
    mejor, mejor_n = None, -1        # cuadro con más personas (se muestra si no hay evento)
    while i < fps * MAX_SEG_VIDEO:
        ok, frame = cap.read()
        if not ok:
            break
        if i % paso == 0:
            incumplen, n, anotada = analizar(frame)
            analizadas += 1
            pers_max = max(pers_max, n)
            if n > mejor_n:
                mejor, mejor_n = anotada.copy(), n
            if incumplen:
                seguidas += 1
                if seguidas >= MUESTRAS_ALERTA and armado:
                    armado = False
                    eid, nombre, fc, fch = guardar_evento(anotada, incumplen, zona, lat, lon, prec, "app")
                    eventos.append(dict(id=eid, imagen=f"/capturas/{nombre}", falta_casco=fc, falta_chaleco=fch))
            else:
                seguidas = 0
                armado = True
        i += 1
    cap.release()
    Path(ruta_tmp).unlink(missing_ok=True)
    if analizadas == 0:
        return jsonify(error="No pude leer el video"), 400
    out = dict(tipo="video", muestras=analizadas, personas=pers_max, incumplimientos=len(eventos), eventos=eventos,
               con_ubicacion=lat is not None)
    if eventos:
        out["imagen"] = eventos[0]["imagen"]
    elif mejor is not None:
        tmp = CAPTURAS / f"app_ok_{int(time.time() * 1000)}.jpg"
        cv2.imwrite(str(tmp), mejor)
        out["imagen"] = f"/capturas/{tmp.name}"
    return jsonify(out)


@app.get("/api/eventos")
def api_eventos():
    con = db.conectar(BD)
    try:
        ev = db.eventos_dict(con)
        for e in ev:
            e["imagen"] = "/capturas/" + Path(e["ruta_captura"] or "").name
        rep = [dict(zona=z, hora=h, eventos=n, sin_casco=c, sin_chaleco=ch) for z, h, n, c, ch in db.reporte_zona_hora(con)]
        return jsonify(eventos=ev, reporte=rep)
    finally:
        con.close()


@app.get("/capturas/<path:nombre>")
def capturas(nombre):
    return send_from_directory(CAPTURAS, nombre)


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
    """Abre un túnel de Cloudflare (sin cuenta) y devuelve su URL pública https."""
    exe = shutil.which("cloudflared") or str(Path.home() / ".local" / "bin" / "cloudflared")
    if not Path(exe).exists():
        raise SystemExit("No encuentro cloudflared. Instálalo (ver README, sección «Desde cualquier red»).")
    proc = subprocess.Popen([exe, "tunnel", "--url", f"http://localhost:{puerto}", "--no-autoupdate"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url = []

    def leer():
        for linea in proc.stdout:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", linea)
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
    ap.add_argument("--publico", action="store_true", help="URL pública con túnel de Cloudflare (cualquier red)")
    ap.add_argument("--clave", help="contraseña de acceso (usuario «epp»); con --publico se genera una si no la das")
    a = ap.parse_args()
    if a.publico and not (a.clave or CLAVE):
        a.clave = secrets.token_urlsafe(8)
    if a.clave:
        CLAVE = a.clave
    if a.publico:
        url, _tunel = iniciar_tunel(a.puerto)
        print(f"\n  App pública:  {url}\n  Panel:        {url}/panel\n  Usuario: epp   Clave: {CLAVE}\n")
    app.run(host="127.0.0.1" if a.publico else "0.0.0.0", port=a.puerto,
            ssl_context="adhoc" if a.https and not a.publico else None, threaded=True)
