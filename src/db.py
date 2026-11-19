"""Conexión y consultas a la base SQLite de eventos."""
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
COLUMNAS_NUEVAS = {"latitud": "REAL", "longitud": "REAL", "precision_m": "REAL", "origen": "TEXT DEFAULT 'video'"}


def conectar(ruta):
    con = sqlite3.connect(ruta)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    # migración: bases creadas antes de agregar la ubicación
    existentes = {r[1] for r in con.execute("PRAGMA table_info(eventos)")}
    for col, tipo in COLUMNAS_NUEVAS.items():
        if col not in existentes:
            con.execute(f"ALTER TABLE eventos ADD COLUMN {col} {tipo}")
    con.commit()
    return con


def registrar_evento(con, zona, falta_casco, falta_chaleco, confianza, ruta_captura,
                     latitud=None, longitud=None, precision_m=None, origen="video"):
    cur = con.execute(
        "INSERT INTO eventos (momento, zona, falta_casco, falta_chaleco, confianza, ruta_captura, "
        "latitud, longitud, precision_m, origen) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), zona, int(falta_casco), int(falta_chaleco),
         float(confianza), str(ruta_captura), latitud, longitud, precision_m, origen))
    con.commit()
    return cur.lastrowid


def todos(con):
    return con.execute("SELECT * FROM eventos ORDER BY id").fetchall()


def eventos_dict(con):
    con.row_factory = sqlite3.Row
    filas = [dict(r) for r in con.execute("SELECT * FROM eventos ORDER BY id DESC")]
    con.row_factory = None
    return filas


def reporte_zona_hora(con):
    """Incumplimientos por zona y por hora del día (reto extra del proyecto)."""
    return con.execute(
        "SELECT zona, substr(momento, 12, 2) AS hora, COUNT(*) AS eventos, "
        "SUM(falta_casco) AS sin_casco, SUM(falta_chaleco) AS sin_chaleco "
        "FROM eventos GROUP BY zona, hora ORDER BY zona, hora").fetchall()
