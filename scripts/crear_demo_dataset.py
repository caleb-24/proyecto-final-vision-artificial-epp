"""Arma demo_dataset.mp4 con imágenes del conjunto de prueba (NO es una grabación real).
Alterna personas con equipo completo y personas sin casco o sin chaleco."""
import random, sys
from pathlib import Path
import cv2

RAIZ = Path(__file__).resolve().parents[1]
R = Path(sys.argv[1]) / "test"   # carpeta del dataset
random.seed(7)
con, sin = [], []
for lbl in sorted((R / "labels").glob("*.txt")):
    filas = [l.split() for l in lbl.read_text().splitlines() if l.strip()]
    cls = [f[0] for f in filas]
    if cls.count("2") != 1:
        continue
    _, cx, cy, w, h = map(float, next(f for f in filas if f[0] == "2"))
    # persona completa y visible: no pegada a los bordes, tamaño razonable
    if not (0.35 <= h <= 0.9 and w <= 0.7 and cy - h / 2 > 0.03 and cy + h / 2 < 0.97 and cx - w / 2 > 0.03 and cx + w / 2 < 0.97):
        continue
    img = R / "images" / (lbl.stem + ".jpg")
    if not img.exists():
        continue
    if "0" in cls and "1" in cls:
        con.append(img)
    elif "0" not in cls or "1" not in cls:
        sin.append(img)
random.shuffle(con); random.shuffle(sin)
FPS, SEG, T = 25, 3, 960
out = cv2.VideoWriter(str(RAIZ / "demo" / "demo_dataset.mp4"),
                      cv2.VideoWriter_fourcc(*"mp4v"), FPS, (T, T))
for a, b in zip(con[:5], sin[:5]):
    for img in (a, b):
        f = cv2.resize(cv2.imread(str(img)), (T, T))
        cv2.putText(f, "DEMO: imagen del dataset", (10, T - 15), 0, 0.8, (255, 255, 255), 2)
        for _ in range(FPS * SEG):
            out.write(f)
out.release()
print("Listo: demo_dataset.mp4", len(con), len(sin))
