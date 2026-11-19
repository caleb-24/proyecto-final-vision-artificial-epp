from pathlib import Path
from ultralytics import YOLO

ROOT = Path("/home/home/Documentos/caleb/iot/proyecto final/safety-Helmet-Reflective-Jacket")
EXT = {".jpg", ".jpeg", ".png"}
PERSONA_ID = 2

model = YOLO("yolov8n.pt")

for split in ["train", "valid", "test"]:
    for img in sorted((ROOT / split / "images").iterdir()):
        if img.suffix.lower() not in EXT:
            continue
        res = model.predict(str(img), classes=[0], conf=0.4, device=0, verbose=False)[0]
        cajas = res.boxes.xywhn.tolist()
        if not cajas:
            continue
        lbl = ROOT / split / "labels" / (img.stem + ".txt")
        with open(lbl, "a", encoding="utf-8") as f:
            f.write("\n" + "\n".join(f"{PERSONA_ID} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for x, y, w, h in cajas) + "\n")
    print(f"{split} listo")
