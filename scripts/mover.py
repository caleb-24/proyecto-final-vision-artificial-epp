import random, shutil
from pathlib import Path

ROOT = Path("/home/home/Documentos/caleb/iot/proyecto final/safety-Helmet-Reflective-Jacket")
EXT = {".jpg", ".jpeg", ".png"}

random.seed(42)
imgs = sorted(p for p in (ROOT / "test" / "images").iterdir() if p.suffix.lower() in EXT)
elegidas = random.sample(imgs, 525)

for img in elegidas:
    lbl = ROOT / "test" / "labels" / (img.stem + ".txt")
    shutil.move(str(img), ROOT / "valid" / "images" / img.name)
    if lbl.exists():
        shutil.move(str(lbl), ROOT / "valid" / "labels" / lbl.name)

print(f"Movidas {len(elegidas)} imágenes de test a valid")
