from pathlib import Path
import re

ROOT = Path("/home/home/Documentos/caleb/iot/proyecto final/safety-Helmet-Reflective-Jacket")
YAML = ROOT / "data.yaml"
IMG_EXT = {".jpg", ".jpeg", ".png"}
SPLITS = ["train", "valid", "test"]

clases_global = set()
conteos = {}
problemas = []

for split in SPLITS:
    img_dir = ROOT / split / "images"
    lbl_dir = ROOT / split / "labels"
    if not img_dir.is_dir() or not lbl_dir.is_dir():
        problemas.append(f"[{split}] falta images o labels")
        continue

    imgs = [p for p in img_dir.iterdir() if p.suffix.lower() in IMG_EXT]
    lbls = list(lbl_dir.glob("*.txt"))
    conteos[split] = len(imgs)

    img_stems = {p.stem for p in imgs}
    lbl_stems = {p.stem for p in lbls}
    sin_lbl = len(img_stems - lbl_stems)
    sin_img = lbl_stems - img_stems
    if sin_img:
        problemas.append(f"[{split}] {len(sin_img)} .txt sin imagen")

    malas = 0
    for lbl in lbls:
        for i, linea in enumerate(lbl.read_text(encoding="utf-8").splitlines(), 1):
            if not linea.strip():
                continue
            p = linea.split()
            try:
                cls = int(p[0])
                vals = [float(x) for x in p[1:]]
            except ValueError:
                malas += 1
                continue
            if len(p) != 5 or not all(0.0 <= v <= 1.0 for v in vals):
                malas += 1
                continue
            clases_global.add(cls)
    if malas:
        problemas.append(f"[{split}] {malas} líneas mal formadas")
    print(f"[{split}] imágenes: {len(imgs)}  etiquetas: {len(lbls)}  sin etiqueta: {sin_lbl}")

total = sum(conteos.values())
print(f"\nTotal: {total}")
for s, n in conteos.items():
    print(f"  {s}: {n / total * 100:.1f}%")

print(f"\nClases en las etiquetas: {sorted(clases_global)}")
if YAML.exists():
    texto = YAML.read_text(encoding="utf-8")
    m = re.search(r"names:\s*\[(.*?)\]", texto, re.S)
    if m:
        nombres = [n.strip().strip("'\"") for n in m.group(1).split(",") if n.strip()]
    else:
        nombres = re.findall(r"^\s*\d+:\s*(.+)$", texto, re.M)
    print("Nombres en data.yaml:")
    for i, n in enumerate(nombres):
        print(f"  {i} -> {n}")
    fuera = [c for c in clases_global if c >= len(nombres)]
    if fuera:
        problemas.append(f"IDs {fuera} no existen en data.yaml")
else:
    problemas.append("No encontré data.yaml")

print("\n=== PROBLEMAS ===")
print("\n".join(problemas) or "Ninguno, la estructura está bien")
