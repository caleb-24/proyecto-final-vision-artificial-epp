"""Conexión y consultas de eventos.

Con SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY definidas (variables de entorno o
archivo .env en la raíz del repositorio) usa Supabase: tabla `eventos` por
PostgREST y capturas en el bucket de Storage. Sin esas variables usa la base
SQLite local, para que el sistema siga funcionando sin conexión.
"""
import os
import secrets
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]
SCHEMA = RAIZ / "db" / "schema.sql"
COLUMNAS_NUEVAS = {"latitud": "REAL", "longitud": "REAL", "precision_m": "REAL", "origen": "TEXT DEFAULT 'video'", "usuario": "TEXT"}


def _cargar_env(ruta):
    """Lee .env simple (CLAVE=valor) sin sobrescribir variables ya definidas."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip("\"'"))


_cargar_env(RAIZ / ".env")
URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
CLAVE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
BUCKET = os.environ.get("SUPABASE_BUCKET", "capturas")


class Supabase:
    """Backend remoto: PostgREST para eventos y Storage para las capturas."""

    def __init__(self, url, clave, bucket=BUCKET):
        self.url, self.bucket = url, bucket
        self.s = requests.Session()
        self.s.headers.update({"apikey": clave, "Authorization": "Bearer " + clave})

    def _req(self, metodo, ruta, **kw):
        r = self.s.request(metodo, self.url + ruta, timeout=30, **kw)
        if not r.ok:
            raise RuntimeError(f"Supabase {metodo} {ruta}: {r.status_code} {r.text[:300]}")
        return r

    def registrar_evento(self, zona, falta_casco, falta_chaleco, confianza, ruta_captura,
                         latitud=None, longitud=None, precision_m=None, origen="video", usuario=None):
        archivo = Path(ruta_captura)
        url_publica = str(ruta_captura)
        if archivo.exists() and archivo.stat().st_size:
            nombre = f"{archivo.stem}_{secrets.token_hex(4)}{archivo.suffix}"
            self._req("POST", f"/storage/v1/object/{self.bucket}/{nombre}",
                      headers={"Content-Type": "image/jpeg", "x-upsert": "true"},
                      data=archivo.read_bytes())
            url_publica = f"{self.url}/storage/v1/object/public/{self.bucket}/{nombre}"
        fila = {
            "momento": datetime.now().isoformat(timespec="seconds"),
            "zona": zona,
            "falta_casco": int(falta_casco),
            "falta_chaleco": int(falta_chaleco),
            "confianza": float(confianza),
            "ruta_captura": url_publica,
            "latitud": latitud,
            "longitud": longitud,
            "precision_m": precision_m,
            "origen": origen,
            "usuario": usuario,
        }
        r = self._req("POST", "/rest/v1/eventos",
                      headers={"Prefer": "return=representation"}, json=fila)
        return r.json()[0]["id"]

    def todos(self):
        return self._req("GET", "/rest/v1/eventos?select=*&order=id.asc").json()

    def eventos_dict(self):
        return self._req("GET", "/rest/v1/eventos?select=*&order=id.desc").json()

    def reporte_zona_hora(self):
        filas = self._req("GET", "/rest/v1/eventos?select=zona,momento,falta_casco,falta_chaleco&order=id.asc").json()
        grupos = defaultdict(lambda: [0, 0, 0])
        for f in filas:
            clave = (f["zona"], str(f["momento"])[11:13])
            grupos[clave][0] += 1
            grupos[clave][1] += int(f.get("falta_casco") or 0)
            grupos[clave][2] += int(f.get("falta_chaleco") or 0)
        return [(z, h, n, c, ch) for (z, h), (n, c, ch) in sorted(grupos.items())]

    def close(self):
        pass


class SQLite:
    """Backend local (compatibilidad y funcionamiento sin internet)."""

    def __init__(self, ruta=None):
        self.ruta = Path(ruta) if ruta else RAIZ / "eventos.db"

    def abrir(self):
        con = sqlite3.connect(self.ruta)
        con.executescript(SCHEMA.read_text(encoding="utf-8"))
        existentes = {r[1] for r in con.execute("PRAGMA table_info(eventos)")}
        for col, tipo in COLUMNAS_NUEVAS.items():
            if col not in existentes:
                con.execute(f"ALTER TABLE eventos ADD COLUMN {col} {tipo}")
        con.commit()
        return con

    def registrar_evento(self, zona, falta_casco, falta_chaleco, confianza, ruta_captura,
                         latitud=None, longitud=None, precision_m=None, origen="video", usuario=None):
        con = self.abrir()
        try:
            cur = con.execute(
                "INSERT INTO eventos (momento, zona, falta_casco, falta_chaleco, confianza, ruta_captura, "
                "latitud, longitud, precision_m, origen, usuario) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), zona, int(falta_casco), int(falta_chaleco),
                 float(confianza), str(ruta_captura), latitud, longitud, precision_m, origen, usuario))
            con.commit()
            return cur.lastrowid
        finally:
            con.close()

    def todos(self):
        con = self.abrir()
        try:
            return con.execute("SELECT * FROM eventos ORDER BY id").fetchall()
        finally:
            con.close()

    def eventos_dict(self):
        con = self.abrir()
        try:
            con.row_factory = sqlite3.Row
            return [dict(r) for r in con.execute("SELECT * FROM eventos ORDER BY id DESC")]
        finally:
            con.close()

    def reporte_zona_hora(self):
        con = self.abrir()
        try:
            return con.execute(
                "SELECT zona, substr(momento, 12, 2) AS hora, COUNT(*) AS eventos, "
                "SUM(falta_casco) AS sin_casco, SUM(falta_chaleco) AS sin_chaleco "
                "FROM eventos GROUP BY zona, hora ORDER BY zona, hora").fetchall()
        finally:
            con.close()

    def close(self):
        pass


_ACTIVO = None


def conectar(ruta=None):
    """Devuelve el backend activo. `ruta` solo aplica al modo SQLite local."""
    global _ACTIVO
    if _ACTIVO is None:
        _ACTIVO = Supabase(URL, CLAVE) if URL and CLAVE else SQLite(ruta)
    return _ACTIVO


def registrar_evento(con, *args, **kwargs):
    return con.registrar_evento(*args, **kwargs)


def todos(con):
    return con.todos()


def eventos_dict(con):
    return con.eventos_dict()


def reporte_zona_hora(con):
    return con.reporte_zona_hora()
