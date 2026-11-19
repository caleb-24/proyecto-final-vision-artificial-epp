"""Sistema de detección de EPP: video -> YOLO -> asociación persona-equipo -> zona -> alerta -> SQLite."""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

import db
from detector import equipo_con_conf, faltas_persona, separar

RAIZ = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("fuente", help="ruta del video, o 0 para la webcam")
ap.add_argument("--redefinir-zona", action="store_true", help="volver a marcar la zona")
ap.add_argument("--zona", help='puntos "x1,y1;x2,y2;x3,y3;..." (sin ventana)')
ap.add_argument("--conf", type=float, default=0.4, help="umbral de confianza de YOLO")
ap.add_argument("--cuadros", type=int, default=15, help="cuadros seguidos para disparar la alerta")
ap.add_argument("--salida", default=str(RAIZ / "demo_anotada.mp4"))
args = ap.parse_args()

MODELO = RAIZ / "models" / "best.pt"
FUENTE = int(args.fuente) if args.fuente.isdigit() else args.fuente
ZONA_JSON = RAIZ / "zona.json"
SALIDA_VIDEO = args.salida
CAPTURAS = RAIZ / "capturas"
CONF = args.conf
CUADROS_ALERTA = args.cuadros

CAPTURAS.mkdir(exist_ok=True)
con = db.conectar(RAIZ / "eventos.db")

def definir_zona(frame):
    puntos = []
    titulo = "Zona: haz 4 clics y presiona Enter"
    def clic(evento, x, y, *_):
        if evento == cv2.EVENT_LBUTTONDOWN:
            puntos.append((x, y))
    cv2.namedWindow(titulo)
    cv2.setMouseCallback(titulo, clic)
    while True:
        dibujo = frame.copy()
        for p in puntos:
            cv2.circle(dibujo, p, 5, (255, 0, 0), -1)
        if len(puntos) > 1:
            cv2.polylines(dibujo, [np.array(puntos)], len(puntos) > 3, (255, 0, 0), 2)
        cv2.imshow(titulo, dibujo)
        if cv2.waitKey(30) & 0xFF == 13 and len(puntos) >= 3:
            break
    cv2.destroyAllWindows()
    return np.array(puntos, dtype=np.int32)

modelo = YOLO(str(MODELO))
DISPOSITIVO = 0 if __import__("torch").cuda.is_available() else "cpu"
cap = cv2.VideoCapture(FUENTE)
fps = cap.get(cv2.CAP_PROP_FPS) or 25
ok, primer = cap.read()
if not ok:
    sys.exit(f"No pude abrir el video: {FUENTE}")
if args.zona:
    zona = np.array([[int(v) for v in p.split(",")] for p in args.zona.split(";")], dtype=np.int32)
elif ZONA_JSON.exists() and not args.redefinir_zona:
    zona = np.array(json.loads(ZONA_JSON.read_text()), dtype=np.int32)
    print("Zona cargada de zona.json (usa --redefinir-zona para cambiarla)")
else:
    zona = definir_zona(primer)
ZONA_JSON.write_text(json.dumps(zona.tolist()))
cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
ancho, alto = int(cap.get(3)), int(cap.get(4))
out = cv2.VideoWriter(SALIDA_VIDEO, cv2.VideoWriter_fourcc(*"mp4v"), fps, (ancho, alto))


VERDE, ROJO, AZUL, AMARILLO, NARANJA = (60, 200, 60), (40, 40, 230), (255, 120, 0), (0, 220, 255), (0, 140, 255)
FUENTE_TXT = cv2.FONT_HERSHEY_SIMPLEX
esc = max(ancho, alto) / 960          # escala de textos según la resolución
grosor = max(2, int(2 * esc))
ZONA_NOMBRE = "Zona 1"
MARGEN_SUP = int(50 * esc)   # alto de la barra superior

def etiqueta(img, texto, x, y, color, tam=0.6, txt=(255, 255, 255)):
    """Texto con fondo de color, dentro de la imagen."""
    t = tam * esc
    (w, h), base = cv2.getTextSize(texto, FUENTE_TXT, t, max(1, grosor - 1))
    x = int(max(0, min(x, img.shape[1] - w - 8)))
    y = int(max(h + 8 + MARGEN_SUP, y))
    cv2.rectangle(img, (x, y - h - 8), (x + w + 8, y + base - 2), color, -1)
    cv2.putText(img, texto, (x + 4, y - 4), FUENTE_TXT, t, txt, max(1, grosor - 1), cv2.LINE_AA)

cuadro = 0
contador = 0
alertado = False
n_eventos = 0
ultimo = (False, False, 0.0)

while True:
    ok, frame = cap.read()
    if not ok:
        break
    cuadro += 1
    res = modelo(frame, conf=CONF, device=DISPOSITIVO, verbose=False)[0]
    cascos, chalecos, personas = separar(res)

    # zona: relleno translúcido + borde
    capa = frame.copy()
    cv2.fillPoly(capa, [zona], AZUL)
    frame = cv2.addWeighted(capa, 0.15, frame, 0.85, 0)
    cv2.polylines(frame, [zona], True, AZUL, grosor + 1, cv2.LINE_AA)
    zx, zy = zona.min(axis=0)
    etiqueta(frame, "ZONA RESTRINGIDA", zx + 4, zy + MARGEN_SUP + int(24 * esc), AZUL, 0.5)

    # equipo detectado: caja fina + etiqueta en su borde inferior
    cascos_c, chalecos_c = equipo_con_conf(res)
    for b, cf in cascos_c:
        cv2.rectangle(frame, tuple(map(int, b[:2])), tuple(map(int, b[2:])), AMARILLO, grosor, cv2.LINE_AA)
        etiqueta(frame, f"Casco {cf:.0%}", b[0], b[3] - 2, AMARILLO, 0.5, (0, 0, 0))
    for b, cf in chalecos_c:
        cv2.rectangle(frame, tuple(map(int, b[:2])), tuple(map(int, b[2:])), NARANJA, grosor, cv2.LINE_AA)
        etiqueta(frame, f"Chaleco {cf:.0%}", b[0], b[3] - 2, NARANJA, 0.5, (0, 0, 0))

    conflicto = False
    fc_f = fch_f = False
    cf_f = 0.0
    for p, pc in personas:
        en_zona = cv2.pointPolygonTest(zona, ((p[0] + p[2]) / 2, p[3]), False) >= 0
        falta_c, falta_ch = faltas_persona(p, cascos, chalecos)
        x1, y1, x2, y2 = map(int, p)
        if not en_zona:
            color, txt = (170, 170, 170), "Fuera de zona"
        elif falta_c or falta_ch:
            conflicto = True
            fc_f |= falta_c
            fch_f |= falta_ch
            cf_f = max(cf_f, float(pc))
            color = ROJO
            faltas = " y ".join(n for n, f in (("CASCO", falta_c), ("CHALECO", falta_ch)) if f)
            txt = f"SIN {faltas}"
        else:
            color, txt = VERDE, "EPP completo"
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, grosor + 1, cv2.LINE_AA)
        etiqueta(frame, f"Persona: {txt} {pc:.0%}", x1, y1 - 2, color)

    if conflicto:
        contador += 1
        ultimo = (fc_f, fch_f, cf_f)
    else:
        contador = 0
        alertado = False
    nuevo = contador >= CUADROS_ALERTA and not alertado
    if nuevo:
        alertado = True
        n_eventos += 1

    # barra superior (HUD)
    cv2.rectangle(frame, (0, 0), (ancho, int(44 * esc)), (30, 30, 30), -1)
    cv2.putText(frame, f"Detector EPP | {ZONA_NOMBRE} | t={cuadro / fps:5.1f}s | Eventos: {n_eventos}",
                (10, int(30 * esc)), FUENTE_TXT, 0.7 * esc, (255, 255, 255), max(1, grosor - 1), cv2.LINE_AA)
    if conflicto and not alertado:   # falta detectada, acumulando cuadros
        pct = min(1.0, contador / CUADROS_ALERTA)
        cv2.rectangle(frame, (0, int(44 * esc)), (int(ancho * pct), int(50 * esc)), NARANJA, -1)
    if alertado:                     # alerta activa: borde rojo parpadeante + banner
        if (cuadro // 6) % 2 == 0:
            cv2.rectangle(frame, (0, 0), (ancho - 1, alto - 1), ROJO, int(8 * esc))
        fc, fch, _ = ultimo
        falta = " / ".join(n for n, f in (("SIN CASCO", fc), ("SIN CHALECO", fch)) if f)
        cv2.rectangle(frame, (0, alto - int(60 * esc)), (ancho, alto), ROJO, -1)
        cv2.putText(frame, f"ALERTA: {falta}", (15, alto - int(18 * esc)),
                    FUENTE_TXT, 1.1 * esc, (255, 255, 255), grosor + 1, cv2.LINE_AA)

    if nuevo:
        fc, fch, cf = ultimo
        ruta = CAPTURAS / f"evento_{cuadro}.jpg"
        cv2.imwrite(str(ruta), frame)
        db.registrar_evento(con, ZONA_NOMBRE, fc, fch, cf, ruta)
        print("Evento guardado:", ruta.name)
    out.write(frame)

cap.release()
out.release()
con.close()
print("Listo. Cuadros procesados:", cuadro)
