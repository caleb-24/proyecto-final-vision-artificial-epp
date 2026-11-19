"""Reporte de incumplimientos por zona y por hora, consultado desde la base de datos."""
import argparse
from pathlib import Path
import db

RAIZ = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--bd", default=str(RAIZ / "eventos.db"))
args = ap.parse_args()
con = db.conectar(args.bd)
print("== Eventos ==")
for r in db.todos(con):
    print(r)
print("\n== Incumplimientos por zona y hora ==")
print(f"{'zona':10} {'hora':5} {'eventos':8} {'sin_casco':10} {'sin_chaleco':11}")
for z, h, n, c, ch in db.reporte_zona_hora(con):
    print(f"{z:10} {h:5} {n:<8} {c:<10} {ch:<11}")
