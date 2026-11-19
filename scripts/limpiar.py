from pathlib import Path

ROOT = Path("/home/home/Documentos/caleb/iot/proyecto final/safety-Helmet-Reflective-Jacket")

for split in ["train", "valid", "test"]:
    cambios = 0
    for lbl in (ROOT / split / "labels").glob("*.txt"):
        original = lbl.read_text(encoding="utf-8").splitlines()
        limpias = []
        for linea in original:
            p = linea.split()
            if len(p) == 5 and p[0] in {"0", "1"}:
                limpias.append(linea)
        if limpias != original:
            lbl.write_text("\n".join(limpias) + "\n", encoding="utf-8")
            cambios += 1
    print(split, "archivos corregidos:", cambios)
