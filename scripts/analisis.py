"""Experimentos del análisis técnico (secciones B, C, D, E del informe).

Uso:  python scripts/analisis.py RUTA_DATASET     (carpeta con test/images y test/labels)
Genera resultados/analisis/*.json y docs/figuras/*.png|jpg
"""
import json
import sys
import time
from pathlib import Path

import cv2
import matplotlib
import numpy as np
import torch
from ultralytics import YOLO

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from detector import asociado_casco, asociado_chaleco  # noqa: E402

TEST = Path(sys.argv[1]) / "test"
OUT = RAIZ / "resultados" / "analisis"
FIG = RAIZ / "docs" / "figuras"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)
DEV = 0 if torch.cuda.is_available() else "cpu"
NOMBRES = {0: "casco", 1: "chaleco", 2: "persona"}
UMBRALES = [round(x, 2) for x in np.arange(0.05, 0.91, 0.05)]
CONF_SISTEMA = 0.4
modelo = YOLO(str(RAIZ / "models" / "best.pt"))
rng = np.random.default_rng(0)


# ------------------------------------------------------------------ utilidades
def leer_gt(lbl):
    filas = []
    for l in lbl.read_text().splitlines():
        p = l.split()
        if len(p) == 5:
            c, x, y, w, h = int(p[0]), *map(float, p[1:])
            filas.append((c, x - w / 2, y - h / 2, x + w / 2, y + h / 2))
    return np.array(filas, dtype=float).reshape(-1, 5)


def iou(a, B):
    if len(B) == 0:
        return np.zeros(0)
    x1 = np.maximum(a[0], B[:, 0]); y1 = np.maximum(a[1], B[:, 1])
    x2 = np.minimum(a[2], B[:, 2]); y2 = np.minimum(a[3], B[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (B[:, 2] - B[:, 0]) * (B[:, 3] - B[:, 1]) - inter
    return inter / np.maximum(ua, 1e-9)


def predecir(entradas, conf=0.05, lote=16):
    """Devuelve lista de arrays Nx6 [cls, conf, x1, y1, x2, y2] normalizados (procesa por lotes)."""
    salida = []
    for k in range(0, len(entradas), lote):
        for r in modelo.predict(entradas[k:k + lote], conf=conf, device=DEV, verbose=False):
            b = r.boxes
            salida.append(np.column_stack([b.cls.cpu().numpy(), b.conf.cpu().numpy(), b.xyxyn.cpu().numpy()])
                          if len(b) else np.zeros((0, 6)))
    return salida


def pr_deteccion(P, G, t, clase=None):
    """Precisión/recall de detección (IoU>=0.5, misma clase) a umbral t."""
    tp = fp = fn = 0
    for stem in G:
        g = G[stem]
        p = P[stem]
        p = p[p[:, 1] >= t]
        for c in ([clase] if clase is not None else [0, 1, 2]):
            gc = g[g[:, 0] == c][:, 1:]
            pc = p[p[:, 0] == c]
            pc = pc[np.argsort(-pc[:, 1])]
            usado = np.zeros(len(gc), bool)
            for d in pc:
                i = iou(d[2:], gc)
                i[usado] = 0
                if len(i) and i.max() >= 0.5:
                    usado[i.argmax()] = True; tp += 1
                else:
                    fp += 1
            fn += int((~usado).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return pr, rc, 2 * pr * rc / max(pr + rc, 1e-9)


# --------------------------------------------- regla de asociación (dos versiones)
def regla_final(persona, cascos, chalecos):
    return (not any(asociado_casco(persona, c) for c in cascos),
            not any(asociado_chaleco(persona, c) for c in chalecos))


def regla_simple(persona, cascos, chalecos):
    """Versión inicial: basta que el centro del equipo caiga en cualquier parte de la persona."""
    def dentro(p, c):
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        return p[0] <= cx <= p[2] and p[1] <= cy <= p[3]
    return (not any(dentro(persona, c) for c in cascos), not any(dentro(persona, c) for c in chalecos))


def sistema(P, G, t, regla, guardar_fallas=False):
    """Evalúa la decisión del sistema por persona: ¿incumple (falta casco o chaleco)?"""
    tp = fp = fn = tn = perdidas = 0
    acc_c = acc_ch = n = 0
    fallas = []
    for stem in G:
        g = G[stem]
        p = P[stem]
        p = p[p[:, 1] >= t]
        gc = [b[1:] for b in g if b[0] == 0]
        gj = [b[1:] for b in g if b[0] == 1]
        pc = [b[2:] for b in p if b[0] == 0]
        pj = [b[2:] for b in p if b[0] == 1]
        pp = p[p[:, 0] == 2]
        for gp in g[g[:, 0] == 2]:
            gbox = gp[1:]
            real_c, real_ch = regla(gbox, gc, gj)
            i = iou(gbox, pp[:, 2:]) if len(pp) else np.zeros(0)
            if len(i) == 0 or i.max() < 0.5:
                perdidas += 1
                continue
            pbox = pp[i.argmax(), 2:]
            pred_c, pred_ch = regla(pbox, pc, pj)
            real, pred = real_c or real_ch, pred_c or pred_ch
            n += 1; acc_c += pred_c == real_c; acc_ch += pred_ch == real_ch
            if pred and real: tp += 1
            elif pred and not real:
                fp += 1
                if guardar_fallas: fallas.append((stem, "FP", pred_c, pred_ch))
            elif real and not pred:
                fn += 1
                if guardar_fallas: fallas.append((stem, "FN", real_c, real_ch))
            else: tn += 1
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return dict(umbral=t, personas_evaluadas=n, personas_no_detectadas=perdidas, tp=tp, fp=fp, fn=fn, tn=tn,
                precision=pr, recall=rc, f1=2 * pr * rc / max(pr + rc, 1e-9),
                acc_casco=acc_c / max(n, 1), acc_chaleco=acc_ch / max(n, 1)), fallas


# ================================================================== ejecución
imgs = sorted((TEST / "images").glob("*.jpg"))
G = {p.stem: leer_gt(TEST / "labels" / (p.stem + ".txt")) for p in imgs}
print(f"{len(imgs)} imágenes de prueba")
t0 = time.time()
P = dict(zip([p.stem for p in imgs], predecir([str(p) for p in imgs])))
print(f"inferencia completa: {time.time() - t0:.1f}s")
res = {}

# ---- D1: barrido de confianza (detección y sistema)
barrido = []
for t in UMBRALES:
    pr, rc, f1 = pr_deteccion(P, G, t)
    s, _ = sistema(P, G, t, regla_final)
    barrido.append(dict(umbral=t, det_precision=pr, det_recall=rc, det_f1=f1,
                        sis_precision=s["precision"], sis_recall=s["recall"], sis_f1=s["f1"]))
res["barrido_confianza"] = barrido
fig, ax = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
x = [b["umbral"] for b in barrido]
for a, pref, tit in zip(ax, ("det", "sis"), ("Detección de objetos (IoU≥0.5)", "Decisión «incumple» por persona")):
    a.plot(x, [b[f"{pref}_precision"] for b in barrido], "o-", label="Precisión")
    a.plot(x, [b[f"{pref}_recall"] for b in barrido], "s-", label="Recall")
    a.plot(x, [b[f"{pref}_f1"] for b in barrido], "^--", label="F1", color="k")
    a.axvline(CONF_SISTEMA, color="gray", ls=":"); a.set_title(tit); a.set_xlabel("Umbral de confianza"); a.grid(alpha=.3)
ax[0].set_ylabel("Valor"); ax[0].legend()
plt.tight_layout(); plt.savefig(FIG / "fig_barrido_confianza.png", dpi=150); plt.close()
mejor = max(barrido, key=lambda b: b["sis_f1"])
res["mejor_umbral_sistema"] = mejor

# ---- D2: antes/después de la regla de asociación (conf 0.4)
antes, _ = sistema(P, G, CONF_SISTEMA, regla_simple)
despues, fallas = sistema(P, G, CONF_SISTEMA, regla_final, guardar_fallas=True)
res["regla_antes"] = antes; res["regla_despues"] = despues

# ---- por clase a conf 0.4
res["deteccion_por_clase_conf04"] = {NOMBRES[c]: dict(zip(("precision", "recall", "f1"), pr_deteccion(P, G, CONF_SISTEMA, c)))
                                     for c in (0, 1, 2)}

# ---- casos de falla: imágenes anotadas
def dibujar(stem, t=CONF_SISTEMA):
    im = cv2.imread(str(TEST / "images" / (stem + ".jpg")))
    h, w = im.shape[:2]
    col = {0: (0, 220, 255), 1: (0, 140, 255), 2: (60, 200, 60)}
    for b in P[stem]:
        if b[1] < t: continue
        x1, y1, x2, y2 = (b[2:] * [w, h, w, h]).astype(int)
        cv2.rectangle(im, (x1, y1), (x2, y2), col[int(b[0])], 2)
        cv2.putText(im, f"{NOMBRES[int(b[0])]} {b[1]:.2f}", (x1, max(y1 - 5, 12)), 0, 0.5, col[int(b[0])], 1)
    for g in G[stem]:
        x1, y1, x2, y2 = (g[1:] * [w, h, w, h]).astype(int)
        cv2.rectangle(im, (x1, y1), (x2, y2), (255, 255, 255), 1, cv2.LINE_4)
    return im
for k, tipo in enumerate(("FP", "FN")):
    sel = [f for f in fallas if f[1] == tipo]
    rng.shuffle(sel)
    for j, (stem, tp_, a, b) in enumerate(sel[:8]):
        cv2.imwrite(str(FIG / f"candidato_{tipo}_{j}_{stem}.jpg"), dibujar(stem))
res["fallas_totales"] = {"FP": sum(f[1] == "FP" for f in fallas), "FN": sum(f[1] == "FN" for f in fallas)}

# ---- B: efecto de la distancia (tamaño de la persona) y la iluminación natural
bril = {s: float(cv2.cvtColor(cv2.imread(str(TEST / "images" / (s + ".jpg"))), cv2.COLOR_BGR2GRAY).mean()) for s in G}
def recall_persona(stems):
    tp = n = 0
    for s in stems:
        pp = P[s][(P[s][:, 0] == 2) & (P[s][:, 1] >= CONF_SISTEMA)]
        for g in G[s][G[s][:, 0] == 2]:
            n += 1
            i = iou(g[1:], pp[:, 2:]) if len(pp) else np.zeros(0)
            tp += len(i) > 0 and i.max() >= 0.5
    return tp / max(n, 1), n
alt = [(g[4] - g[2], s) for s in G for g in G[s] if g[0] == 2]
bins_alt = [(0, .15, "lejos (<15 %)"), (.15, .4, "media (15–40 %)"), (.4, 1.01, "cerca (>40 %)")]
dist = []
for lo, hi, nom in bins_alt:
    n_tp = n = 0
    for s in G:
        pp = P[s][(P[s][:, 0] == 2) & (P[s][:, 1] >= CONF_SISTEMA)]
        for g in G[s][G[s][:, 0] == 2]:
            hh = g[4] - g[2]
            if lo <= hh < hi:
                n += 1
                i = iou(g[1:], pp[:, 2:]) if len(pp) else np.zeros(0)
                n_tp += len(i) > 0 and i.max() >= 0.5
    dist.append(dict(rango=nom, n=n, recall=n_tp / max(n, 1)))
res["recall_persona_por_distancia"] = dist
q = np.quantile(list(bril.values()), [1 / 3, 2 / 3])
ilum_nat = []
for nom, f in (("oscuras", lambda v: v < q[0]), ("medias", lambda v: q[0] <= v < q[1]), ("claras", lambda v: v >= q[1])):
    st = [s for s in G if f(bril[s])]
    r, n = recall_persona(st)
    ilum_nat.append(dict(grupo=nom, brillo_medio=float(np.mean([bril[s] for s in st])), n_personas=n, recall_persona=r))
res["recall_persona_por_iluminacion_natural"] = ilum_nat

# ---- B/C: iluminación sintética y normalización sobre 300 imágenes
sub = list(rng.choice(len(imgs), 300, replace=False))
sub_p = [imgs[i] for i in sub]
Gs = {p.stem: G[p.stem] for p in sub_p}
cargadas = [cv2.resize(cv2.imread(str(p)), (640, 640)) for p in sub_p]
ilum = []
for alpha in (0.25, 0.5, 1.0, 1.5, 2.0):
    ims = [cv2.convertScaleAbs(im, alpha=alpha) for im in cargadas]
    Pa = dict(zip([p.stem for p in sub_p], predecir(ims)))
    fila = dict(factor_brillo=alpha)
    for c in (0, 1, 2):
        fila[NOMBRES[c]] = pr_deteccion(Pa, Gs, CONF_SISTEMA, c)[1]
    fila["F1_global"] = pr_deteccion(Pa, Gs, CONF_SISTEMA)[2]
    ilum.append(fila)
res["iluminacion_sintetica"] = ilum
plt.figure(figsize=(6, 4))
for c in (0, 1, 2):
    plt.plot([f["factor_brillo"] for f in ilum], [f[NOMBRES[c]] for f in ilum], "o-", label=NOMBRES[c])
plt.xlabel("Factor de brillo (1.0 = original)"); plt.ylabel("Recall (conf 0.4)"); plt.grid(alpha=.3); plt.legend()
plt.tight_layout(); plt.savefig(FIG / "fig_iluminacion.png", dpi=150); plt.close()
fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
ax[0].bar([d["rango"] for d in dist], [d["recall"] for d in dist], color="#3b7dd8"); ax[0].set_title("Recall de persona vs tamaño en imagen")
ax[1].bar([d["grupo"] for d in ilum_nat], [d["recall_persona"] for d in ilum_nat], color="#e8923a"); ax[1].set_title("Recall de persona vs brillo natural")
for a in ax: a.set_ylim(0, 1); a.grid(axis="y", alpha=.3)
plt.tight_layout(); plt.savefig(FIG / "fig_distancia_iluminacion.png", dpi=150); plt.close()

# ---- C2: ¿qué pasa sin normalizar la entrada?
rgb = np.stack([cv2.cvtColor(im, cv2.COLOR_BGR2RGB) for im in cargadas]).transpose(0, 3, 1, 2).astype(np.float32)
try:
    from ultralytics.utils.nms import non_max_suppression
except ImportError:  # versiones antiguas
    from ultralytics.utils.ops import non_max_suppression
red = modelo.model.to(DEV if DEV != "cpu" else "cpu").float().eval()


def predecir_crudo(x, conf=0.05):
    """Pasa el tensor directo por la red (sin el reescalado automático de Ultralytics) y aplica NMS."""
    out = []
    for k in range(0, len(x), 25):
        with torch.no_grad():
            y = red(torch.from_numpy(x[k:k + 25]).to(next(red.parameters()).device))
        y = y[0] if isinstance(y, (list, tuple)) else y
        for d in non_max_suppression(y, conf_thres=conf, iou_thres=0.7):
            d = d.cpu().numpy()
            out.append(np.column_stack([d[:, 5], d[:, 4], d[:, :4] / 640]) if len(d) else np.zeros((0, 6)))
    return out


norm = {}
for nombre, esc in (("normalizada (0–1)", 1 / 255), ("sin normalizar (0–255)", 1.0)):
    Pn = dict(zip([p.stem for p in sub_p], predecir_crudo(rgb * esc)))
    pr, rc, f1 = pr_deteccion(Pn, Gs, CONF_SISTEMA)
    nd = sum(int((v[:, 1] >= CONF_SISTEMA).sum()) for v in Pn.values())
    conf_media = float(np.mean([v[v[:, 1] >= 0.05, 1].mean() if (v[:, 1] >= 0.05).any() else 0 for v in Pn.values()]))
    norm[nombre] = dict(precision=pr, recall=rc, f1=f1, detecciones=nd, gt=int(sum(len(g) for g in Gs.values())),
                        confianza_media_dets=conf_media)
res["normalizacion"] = norm

# ---- C1: filtro 3x3 a mano vs OpenCV
gris = cv2.cvtColor(cv2.imread(str(imgs[0])), cv2.COLOR_BGR2GRAY)
cy, cx = gris.shape[0] // 2, gris.shape[1] // 2
parche = gris[cy - 1:cy + 2, cx - 1:cx + 2].astype(np.float64)
kernels = {"Promedio 3x3": np.ones((3, 3)) / 9,
           "Sobel horizontal (Gx)": np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], float),
           "Laplaciano": np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], float)}
filtros = {}
for nom, k in kernels.items():
    a_mano = float((parche * k).sum())
    ocv = float(cv2.filter2D(gris.astype(np.float32), cv2.CV_32F, k.astype(np.float32))[cy, cx])
    filtros[nom] = dict(a_mano=a_mano, opencv=ocv, diferencia=abs(a_mano - ocv))
res["filtro_3x3"] = dict(imagen=imgs[0].name, centro=[cx, cy], parche=parche.astype(int).tolist(), filtros=filtros)

# ---- velocidad
muestra = cargadas[:100]
for dev in (["cpu"] + ([0] if torch.cuda.is_available() else [])):
    modelo.predict(muestra[:3], device=dev, verbose=False)
    t0 = time.time()
    for im in muestra:
        modelo.predict(im, device=dev, verbose=False)
    res[f"fps_{'gpu' if dev == 0 else 'cpu'}"] = len(muestra) / (time.time() - t0)

(OUT / "analisis.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
print(json.dumps({k: v for k, v in res.items() if k != "barrido_confianza"}, indent=1, ensure_ascii=False))
