"""Autenticación de usuarios con Supabase Auth (correo y contraseña).

El navegador y la app móvil guardan solo el access_token; la contraseña nunca
pasa por el servidor más que en el momento de registro / inicio de sesión.
"""
import os
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]


def _cargar_env(ruta):
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
CLAVE = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _cabeceras(token=None):
    h = {"apikey": CLAVE, "Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    return h


def _error(datos, defecto):
    return datos.get("msg") or datos.get("error_description") or datos.get("message") or defecto


def crear_cuenta(email, clave):
    r = requests.post(URL + "/auth/v1/signup", headers=_cabeceras(),
                      json={"email": email, "password": clave}, timeout=25)
    datos = r.json() if r.content else {}
    if r.status_code >= 400:
        raise ValueError(_error(datos, "No se pudo crear la cuenta"))
    token = datos.get("access_token")
    usuario = datos.get("user") or {}
    return {"token": token, "usuario": usuario.get("email") or email,
            "confirma_email": not token}


def iniciar_sesion(email, clave):
    r = requests.post(URL + "/auth/v1/token?grant_type=password", headers=_cabeceras(),
                      json={"email": email, "password": clave}, timeout=25)
    datos = r.json() if r.content else {}
    if r.status_code >= 400:
        raise ValueError(_error(datos, "Correo o contraseña incorrectos"))
    usuario = datos.get("user") or {}
    return {"token": datos.get("access_token"), "usuario": usuario.get("email") or email,
            "confirma_email": False}


def usuario_actual(token):
    """Devuelve el usuario del token, o None si no es válido."""
    if not token:
        return None
    try:
        r = requests.get(URL + "/auth/v1/user", headers=_cabeceras(token), timeout=20)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    return r.json()
